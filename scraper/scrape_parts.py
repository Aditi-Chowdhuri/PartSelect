"""
PartSelect parts scraper v3 — paginated CDX discovery, no server-side regex filter.

CDX strategy: paginate www.partselect.com/PS*.htm in batches of 300 with
collapse=original. Filter by appliance type locally from the URL slug.
This avoids the ReadTimeout that happens with a single large limit+filter query.

Fetch strategy (per part):
  1. Direct PartSelect fetch with stealth headers — individual /PS{n}.htm pages
     are NOT blocked by Akamai (only category listing pages are protected)
  2. Wayback Machine archived snapshot fallback if direct fetch returns non-200

Resumable: completed parts saved incrementally to data/parts_raw.jsonl —
           safe to Ctrl+C and restart, already-scraped parts are skipped.

Output: data/parts_raw.jsonl  (incremental, one JSON object per line)
        data/parts_raw.json   (final consolidated, sorted by review count)

Run: python scrape_parts.py
Est. time: ~25 min for ~1,300 parts (5 concurrent, polite delays)
"""
import asyncio
import json
import re
import random
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from tqdm import tqdm

CDX_API  = "http://web.archive.org/cdx/search/cdx"
WAYBACK  = "https://web.archive.org/web/2023"
BASE_URL = "https://www.partselect.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language":           "en-US,en;q=0.9",
    "Accept-Encoding":           "gzip, deflate, br",
    "Connection":                "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":            "document",
    "Sec-Fetch-Mode":            "navigate",
    "Sec-Fetch-Site":            "none",
}

CONCURRENCY    = 5
DIRECT_DELAY   = (1.0, 2.0)
WAYBACK_DELAY  = 1.2
PARTS_PER_CAT  = 1000    # cap per category; CDX typically has 953 fridge + 395 dish
CDX_PAGE_SIZE  = 300     # rows per CDX request — keeps each request fast
CDX_MAX_PAGES  = 40      # up to 12,000 CDX rows scanned total
CDX_PAGE_DELAY = 1.0     # seconds between CDX page requests (polite)
TIMEOUT        = 40
MAX_RETRIES    = 2


# ── Step 1: Discover part URLs via paginated CDX API ─────────────────────────

async def _cdx_pages(client: httpx.AsyncClient, keyword: str) -> list[tuple[str, str]]:
    """
    Paginate CDX for PS part URLs matching a keyword (Refrigerator / Dishwasher).
    Root fix: omit .htm from the URL pattern — CDX returns [] when the pattern
    has both a wildcard (*) AND a literal suffix (.htm).
    Use keyword filter + collapse=original + offset pagination to stay fast.
    """
    seen_ps: set[str] = set()
    results: list[tuple[str, str]] = []
    offset = 0

    for page_num in range(CDX_MAX_PAGES):
        if len(results) >= PARTS_PER_CAT:
            break
        print(f"    CDX {keyword} page {page_num + 1} (offset={offset}, found={len(results)})")
        try:
            resp = await client.get(
                CDX_API,
                params={
                    "url":      "www.partselect.com/PS*",
                    "output":   "json",
                    "fl":       "original",
                    "filter":   ["statuscode:200", f"original:(?i).*{keyword}.*"],
                    "collapse": "original",
                    "limit":    CDX_PAGE_SIZE,
                    "offset":   offset,
                },
                timeout=60,
            )
            resp.raise_for_status()
        except Exception as exc:
            print(f"    CDX error: {exc} — stopping")
            break

        try:
            data = resp.json()
        except Exception:
            break

        rows = data[1:] if len(data) > 1 else []
        if not rows:
            print(f"    No more rows for {keyword}")
            break

        for row in rows:
            orig_url = row[0].split("?")[0]
            ps_match = re.search(r"/PS(\d+)", orig_url)
            if not ps_match:
                continue
            ps_num = ps_match.group(1)
            if ps_num not in seen_ps:
                seen_ps.add(ps_num)
                results.append((ps_num, orig_url))

        if len(rows) < CDX_PAGE_SIZE:
            break
        offset += CDX_PAGE_SIZE
        await asyncio.sleep(CDX_PAGE_DELAY)

    return results[:PARTS_PER_CAT]


async def discover_part_urls(client: httpx.AsyncClient) -> dict[str, list[tuple[str, str]]]:
    """Returns {'refrigerator': [(ps_num, url), ...], 'dishwasher': [...]}."""
    print("Discovering part URLs via Wayback CDX (paginated)...")
    fridge_urls = await _cdx_pages(client, "Refrigerator")
    dish_urls   = await _cdx_pages(client, "Dishwasher")
    print(f"  Refrigerator: {len(fridge_urls)} unique part URLs")
    print(f"  Dishwasher:   {len(dish_urls)} unique part URLs")
    return {"refrigerator": fridge_urls, "dishwasher": dish_urls}


# ── Step 2: Parse PartSelect HTML ─────────────────────────────────────────────

def parse_part(html: str, ps_num: str, orig_url: str, category: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    if "Page cannot be crawled" in html or "Page Not Found" in html[:2000]:
        return None

    is_wayback = bool(soup.find(id="wm-ipp-inside") or "web.archive.org/web/" in html[:1000])

    # Use the canonical URL from CDX (full slug) — fall back to short form only if needed
    canonical_url = orig_url if orig_url.startswith("https://www.partselect.com/PS") else f"https://www.partselect.com/PS{ps_num}.htm"

    part: dict = {
        "part_number": f"PS{ps_num}",
        "url":         canonical_url,
        "category":    category,
    }

    # ── Name ──────────────────────────────────────────────────────────────────
    h1 = soup.find("h1", class_=re.compile(r"title", re.I)) or soup.find("h1")
    if not h1:
        return None
    name = h1.get_text(strip=True)
    name = re.sub(r"^(Skip to main content|Close)", "", name).strip()
    if len(name) < 5:
        return None
    part["name"] = name

    # ── Price ─────────────────────────────────────────────────────────────────
    price_el = (
        soup.find(attrs={"itemprop": "price"})
        or soup.find("span", class_=re.compile(r"price", re.I))
        or soup.find("div", class_=re.compile(r"price", re.I))
    )
    if price_el:
        raw = price_el.get("content") or price_el.get_text(strip=True)
        m = re.search(r"\d+\.\d{2}", raw.replace(",", ""))
        if m:
            try:
                part["price"] = float(m.group())
            except ValueError:
                pass
    part.setdefault("price", 0.0)

    # ── Availability ──────────────────────────────────────────────────────────
    avail_el = (
        soup.find(class_=re.compile(r"availability|in.?stock", re.I))
        or soup.find(attrs={"itemprop": "availability"})
    )
    if avail_el:
        avail_text = avail_el.get_text(strip=True)
        if re.search(r"in.?stock", avail_text, re.I):
            part["availability"] = "In Stock"
        elif re.search(r"on.?order|back.?order|special.?order", avail_text, re.I):
            part["availability"] = "On Order"
        elif avail_text:
            part["availability"] = avail_text[:50]
    part.setdefault("availability", "")

    # ── Brand (from URL slug) ─────────────────────────────────────────────────
    slug_match = re.search(r"/PS\d+-([A-Za-z]+)-", orig_url)
    part["brand"] = slug_match.group(1) if slug_match else ""

    # ── Manufacturer & MPN ────────────────────────────────────────────────────
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(strip=True)
            if "manufacturer part" in label or label == "mpn":
                part["mpn"] = value
            elif "manufacturer" in label and "part" not in label:
                part["manufacturer"] = value
    if "mpn" not in part:
        mpn_el = soup.find(attrs={"itemprop": "mpn"})
        if mpn_el:
            part["mpn"] = mpn_el.get_text(strip=True)
    part.setdefault("mpn", "")
    part.setdefault("manufacturer", "")

    # ── Description ───────────────────────────────────────────────────────────
    desc = (
        soup.find("div", class_="pd__description")
        or soup.find("div", class_=re.compile(r"description", re.I))
        or soup.find(attrs={"itemprop": "description"})
    )
    part["description"] = desc.get_text(strip=True)[:500] if desc else ""

    # ── Symptoms ──────────────────────────────────────────────────────────────
    symptoms: list[str] = []
    symptom_heading = soup.find(
        string=re.compile(r"fixes the following symptoms|this part fixes", re.I)
    )
    if symptom_heading:
        container = symptom_heading.find_parent()
        if container:
            parent = container.find_parent()
            if parent:
                for li in parent.find_all("li"):
                    text = li.get_text(strip=True)
                    if text and len(text) > 3:
                        symptoms.append(text)
    if not symptoms:
        for el in soup.find_all(class_=re.compile(r"symptom", re.I)):
            text = el.get_text(strip=True)
            if text and 3 < len(text) < 100:
                symptoms.append(text)
    part["symptoms"] = list(dict.fromkeys(symptoms))[:15]

    # ── Installation difficulty & time ────────────────────────────────────────
    difficulty = ""
    install_time = ""

    repair_section = soup.find(class_=re.compile(r"repair.?rating|pd__repair", re.I))
    if repair_section:
        text = repair_section.get_text(" ", strip=True)
        diff_m = re.search(
            r"difficulty[:\s]+([A-Za-z ]+?)(?:\s+time|\s+repair|\s*$)", text, re.I
        )
        time_m = re.search(
            r"(?:repair\s+)?time[:\s]+([\w\s\-]+?)(?:\s+difficulty|\s*$)", text, re.I
        )
        if diff_m:
            difficulty = diff_m.group(1).strip()
        if time_m:
            install_time = time_m.group(1).strip()

    if not difficulty:
        for tag in soup.find_all(string=re.compile(r"difficulty level|repair difficulty", re.I)):
            parent = tag.find_parent()
            if parent:
                sib = parent.find_next_sibling()
                if sib:
                    difficulty = sib.get_text(strip=True)
                    break

    if not install_time:
        for tag in soup.find_all(string=re.compile(r"repair time|install.?time", re.I)):
            parent = tag.find_parent()
            if parent:
                sib = parent.find_next_sibling()
                if sib:
                    install_time = sib.get_text(strip=True)
                    break

    part["install_difficulty"] = difficulty[:50]
    part["install_time"]       = install_time[:50]

    # ── Replaces (superseded part numbers) ────────────────────────────────────
    replaces: list[str] = []
    replaces_heading = soup.find(
        string=re.compile(r"this part replaces|replaces part number", re.I)
    )
    if replaces_heading:
        container = replaces_heading.find_parent()
        if container:
            parent = container.find_parent()
            if parent:
                for el in parent.find_all(["li", "span", "a"]):
                    text = el.get_text(strip=True)
                    if re.match(r"[A-Z0-9]{5,20}$", text):
                        replaces.append(text)
    part["replaces"] = list(dict.fromkeys(replaces))[:20]

    # ── Video URL ─────────────────────────────────────────────────────────────
    video_url = ""
    yt_iframe = soup.find("iframe", src=re.compile(r"youtube\.com|youtu\.be", re.I))
    if yt_iframe:
        video_url = yt_iframe.get("src", "")
    if not video_url:
        yt_el = soup.find(attrs={"data-yt-init": True})
        if yt_el:
            vid_id = yt_el.get("data-yt-init", "")
            if vid_id:
                video_url = f"https://www.youtube.com/watch?v={vid_id}"
    if not video_url:
        yt_link = soup.find("a", href=re.compile(r"youtube\.com|youtu\.be", re.I))
        if yt_link:
            video_url = yt_link.get("href", "")
    part["video_url"] = video_url

    # ── Image ─────────────────────────────────────────────────────────────────
    for img in soup.find_all("img"):
        src = img.get("src", "") or img.get("data-src", "")
        if not src:
            continue
        if is_wayback and "web.archive.org" in src and "im_" in src:
            continue
        classes = " ".join(img.get("class", []))
        if re.search(r"main|product|primary|hero|ps-main", classes, re.I):
            part["image_url"] = src
            break
    part.setdefault(
        "image_url",
        f"https://www.partselect.com/assets/images/parts/PS{ps_num}.jpg",
    )

    # ── Rating ────────────────────────────────────────────────────────────────
    rating_el = soup.find(attrs={"itemprop": "ratingValue"})
    if rating_el:
        try:
            part["rating"] = float(rating_el.get_text(strip=True))
        except ValueError:
            pass
    part.setdefault("rating", 0.0)

    review_el = soup.find(attrs={"itemprop": "reviewCount"})
    if review_el:
        try:
            part["review_count"] = int(review_el.get_text(strip=True).replace(",", ""))
        except ValueError:
            pass
    part.setdefault("review_count", 0)

    # ── Compatible models ─────────────────────────────────────────────────────
    compat = (
        soup.find("div", class_=re.compile(r"crossref|compat|models", re.I))
        or soup.find("section", attrs={"id": re.compile(r"compat|model", re.I)})
    )
    if compat:
        models = [
            a.get_text(strip=True)
            for a in compat.find_all("a", limit=30)
            if re.match(r"[A-Z0-9]{5,15}$", a.get_text(strip=True))
        ]
        part["compatible_models"] = models
    part.setdefault("compatible_models", [])

    return part


# ── Step 3: Fetch with direct-first, Wayback fallback ────────────────────────

async def fetch_direct(client: httpx.AsyncClient, ps_num: str) -> str | None:
    url = f"{BASE_URL}/PS{ps_num}.htm"
    await asyncio.sleep(random.uniform(*DIRECT_DELAY))
    try:
        resp = await client.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 2000:
            return resp.text
    except Exception:
        pass
    return None


async def fetch_wayback(client: httpx.AsyncClient, orig_url: str) -> str | None:
    url = f"{WAYBACK}/{orig_url}"
    await asyncio.sleep(WAYBACK_DELAY)
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = await client.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
                continue
            break
        except Exception:
            break
    return None


async def fetch_and_parse(
    client:     httpx.AsyncClient,
    ps_num:     str,
    orig_url:   str,
    category:   str,
    semaphore:  asyncio.Semaphore,
    jsonl_path: Path,
    done_ids:   set[str],
) -> dict | None:
    if ps_num in done_ids:
        return None

    async with semaphore:
        html   = await fetch_direct(client, ps_num)
        source = "direct"

        if not html:
            html   = await fetch_wayback(client, orig_url)
            source = "wayback"

        if not html:
            return None

        result = parse_part(html, ps_num, orig_url, category)
        if result:
            result["_source"] = source
            with jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
        return result


# ── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    data_dir   = Path("data")
    data_dir.mkdir(exist_ok=True)
    jsonl_path = data_dir / "parts_raw.jsonl"
    json_path  = data_dir / "parts_raw.json"

    # Load already-scraped IDs for resumability
    done_ids: set[str] = set()
    if jsonl_path.exists():
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line.strip())
                    ps = re.search(r"PS(\d+)", obj.get("part_number", ""))
                    if ps:
                        done_ids.add(ps.group(1))
                except Exception:
                    pass
        if done_ids:
            print(f"Resuming: {len(done_ids)} parts already scraped, skipping them.")

    async with httpx.AsyncClient(timeout=90) as client:
        by_cat = await discover_part_urls(client)
        fridge_urls = by_cat["refrigerator"]
        dish_urls   = by_cat["dishwasher"]

        all_targets = (
            [(ps, url, "refrigerator") for ps, url in fridge_urls]
            + [(ps, url, "dishwasher")   for ps, url in dish_urls]
        )
        remaining = [(ps, url, cat) for ps, url, cat in all_targets if ps not in done_ids]
        print(f"\nTargeting {len(all_targets)} parts — {len(remaining)} left to fetch.\n")

        semaphore = asyncio.Semaphore(CONCURRENCY)
        tasks = [
            fetch_and_parse(client, ps, url, cat, semaphore, jsonl_path, done_ids)
            for ps, url, cat in remaining
        ]
        for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks)):
            await coro

    # Consolidate JSONL -> sorted JSON
    all_parts: list[dict] = []
    seen: set[str] = set()
    if jsonl_path.exists():
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line.strip())
                    pn = obj.get("part_number", "")
                    if pn and pn not in seen:
                        seen.add(pn)
                        all_parts.append(obj)
                except Exception:
                    pass

    all_parts.sort(key=lambda p: p.get("review_count", 0), reverse=True)
    json_path.write_text(json.dumps(all_parts, indent=2, ensure_ascii=False), encoding="utf-8")

    fridge_c  = sum(1 for p in all_parts if p["category"] == "refrigerator")
    dish_c    = sum(1 for p in all_parts if p["category"] == "dishwasher")
    direct_c  = sum(1 for p in all_parts if p.get("_source") == "direct")
    wayback_c = sum(1 for p in all_parts if p.get("_source") == "wayback")
    symptom_c = sum(1 for p in all_parts if p.get("symptoms"))
    install_c = sum(1 for p in all_parts if p.get("install_difficulty"))
    price_c   = sum(1 for p in all_parts if p.get("price", 0) > 0)
    video_c   = sum(1 for p in all_parts if p.get("video_url"))

    print(f"\nSaved {len(all_parts)} parts to {json_path}")
    print(f"  Refrigerator:      {fridge_c}")
    print(f"  Dishwasher:        {dish_c}")
    print(f"  Source - direct:   {direct_c}")
    print(f"  Source - wayback:  {wayback_c}")
    print(f"  With price:        {price_c}")
    print(f"  With symptoms:     {symptom_c}")
    print(f"  With install info: {install_c}")
    print(f"  With video:        {video_c}")
    print(f"\nNext: python embed_and_index.py")


if __name__ == "__main__":
    asyncio.run(main())
