"""
PartSelect blog article scraper.

The blog listing page (/blog/) returns 403 to bots, so we use a curated list
of known URLs discovered via Wayback CDX. Each article is fetched from the
Wayback Machine (reliable archived snapshots) and parsed with BeautifulSoup.

Only refrigerator and dishwasher relevant articles are saved.

Output: data/blogs_raw.json

Run: python scrape_blogs.py
"""
import asyncio
import json
import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

WAYBACK  = "https://web.archive.org/web/2023"
OUT_PATH = Path("data/blogs_raw.json")

# All known PartSelect blog post URLs (discovered via Wayback CDX).
# Filtered to appliance-relevant topics only.
KNOWN_URLS = [
    # Refrigerator
    "https://www.partselect.com/blog/fridge-energy-saving-tips/",
    "https://www.partselect.com/blog/fridge-freezing-food/",
    "https://www.partselect.com/blog/fridge-frost-buildup-troubleshoot/",
    "https://www.partselect.com/blog/how-to-fix-a-torn-refrigerator-door-seal/",
    "https://www.partselect.com/blog/how-to-fix-fridge-that-is-too-warm/",
    "https://www.partselect.com/blog/how-to-reset-a-frigidaire-refrigerator/",
    "https://www.partselect.com/blog/how-to-reset-a-ge-profile-ice-maker/",
    "https://www.partselect.com/blog/how-to-use-power-cool-on-a-samsung-fridge/",
    "https://www.partselect.com/blog/how-to-change-your-water-filter/",
    "https://www.partselect.com/blog/ice-maker-troubleshooting/",
    "https://www.partselect.com/blog/repair-or-replace-refrigerator-shelf/",
    # Dishwasher
    "https://www.partselect.com/blog/how-to-clean-a-bosch-dishwasher/",
    "https://www.partselect.com/blog/how-to-fix-frigidaire-dishwasher-not-draining/",
    "https://www.partselect.com/blog/how-to-load-your-dishwasher/",
    "https://www.partselect.com/blog/how-to-reset-a-whirlpool-dishwasher-guide/",
    "https://www.partselect.com/blog/how-to-reset-ge-dishwasher/",
]

FRIDGE_KW   = {"refrigerator", "fridge", "freezer", "ice maker", "ice-maker",
               "compressor", "defrost", "water filter", "frigidaire", "samsung fridge",
               "ge profile", "whirlpool fridge"}
DISHWASHER_KW = {"dishwasher", "bosch dishwasher", "frigidaire dishwasher",
                 "whirlpool dishwasher", "ge dishwasher", "spray arm", "detergent"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _categorize(text: str) -> str:
    t = text.lower()
    if any(k in t for k in DISHWASHER_KW):
        return "dishwasher"
    if any(k in t for k in FRIDGE_KW):
        return "refrigerator"
    return ""


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    """Try direct fetch first, fall back to Wayback snapshot."""
    try:
        r = await client.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        if r.status_code == 200 and len(r.text) > 500:
            return r.text
    except Exception:
        pass

    # Wayback fallback
    path = re.sub(r"^https?://[^/]+", "", url)
    wb_url = f"{WAYBACK}/https://www.partselect.com{path}"
    try:
        r = await client.get(wb_url, headers=HEADERS, timeout=30, follow_redirects=True)
        if r.status_code == 200 and len(r.text) > 500:
            return r.text
    except Exception:
        pass

    return None


def _parse(html: str, url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    # Strip Wayback toolbar noise
    for el in soup.find_all(id=re.compile(r"wm-ipp", re.I)):
        el.decompose()

    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title:
        return None

    category = _categorize(title + " " + url)
    if not category:
        return None

    # Publish date
    pub_date = ""
    for sel in ["time", ".entry-date", ".post-date", ".published", ".date"]:
        el = soup.select_one(sel)
        if el:
            pub_date = el.get_text(strip=True)
            break

    # Main content — try article containers first, then all paragraphs
    content = ""
    for sel in ["article", ".entry-content", ".post-content", ".article-body", "main"]:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(" ", strip=True)
            if len(text) > 200:
                content = text
                break
    if not content:
        paras = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]
        content = " ".join(paras)

    content = re.sub(r"\s{2,}", " ", content).strip()[:3000]
    if len(content) < 100:
        return None

    part_numbers = list(dict.fromkeys(re.findall(r"PS\d{7,10}", content)))

    return {
        "category":     category,
        "title":        title,
        "url":          url,
        "pub_date":     pub_date,
        "content":      content,
        "part_numbers": part_numbers[:20],
    }


async def main() -> None:
    Path("data").mkdir(exist_ok=True)
    blogs: list[dict] = []

    async with httpx.AsyncClient() as client:
        for url in KNOWN_URLS:
            print(f"Fetching: {url}")
            html = await _fetch(client, url)
            if not html:
                print(f"  FAIL: could not fetch")
                continue
            result = _parse(html, url)
            if result:
                blogs.append(result)
                print(f"  OK [{result['category']:13}] {result['title'][:60]}")
            else:
                print(f"  SKIP: not relevant or no content")
            await asyncio.sleep(0.8)

    OUT_PATH.write_text(json.dumps(blogs, indent=2, ensure_ascii=False), encoding="utf-8")

    fridge_c = sum(1 for b in blogs if b["category"] == "refrigerator")
    dish_c   = sum(1 for b in blogs if b["category"] == "dishwasher")
    print(f"\nSaved {len(blogs)} blog articles to {OUT_PATH}")
    print(f"  Refrigerator: {fridge_c}  |  Dishwasher: {dish_c}")
    print("\nNext: python embed_and_index.py")


if __name__ == "__main__":
    asyncio.run(main())
