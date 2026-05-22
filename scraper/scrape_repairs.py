"""
PartSelect repair guide scraper.

Input:  xml/PartSelect.com_Sitemap_Repairs.xml
Output: scraper/data/repairs.json
        scraper/data/symptom_part_map.json

Filters for /Repair/Refrigerator/ and /Repair/Dishwasher/ URLs only.
Fetch strategy per page:
  1. Direct: requests.get with User-Agent header, timeout 15s
  2. Wayback fallback: https://web.archive.org/web/2023/{url} if direct
     returns <1000 chars or fails.
Rate limit: 1 request/second.

Also augments symptom_part_map from existing parts_raw.json symptom data.

Run from the repo root:
    python scraper/scrape_repairs.py
"""

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).resolve().parent.parent
XML_PATH    = REPO_ROOT / "xml" / "PartSelect.com_Sitemap_Repairs.xml"
DATA_DIR    = REPO_ROOT / "scraper" / "data"
PARTS_JSON  = DATA_DIR / "parts_raw.json"
OUT_REPAIRS = DATA_DIR / "repairs.json"
OUT_MAP     = DATA_DIR / "symptom_part_map.json"

WAYBACK_BASE = "https://web.archive.org/web/2023"
HEADERS      = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
RATE_LIMIT   = 1.0   # seconds between requests
MIN_CHARS    = 1000  # minimum acceptable response length


# ── Step 1: Parse sitemap ─────────────────────────────────────────────────────

def parse_sitemap(xml_path: Path) -> list[str]:
    """Return all repair-guide URLs from the sitemap."""
    tree = ET.parse(str(xml_path))
    root = tree.getroot()
    ns   = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
    return urls


def filter_urls(urls: list[str]) -> list[str]:
    """Keep only refrigerator and dishwasher repair pages (not bare category URLs)."""
    filtered = []
    for url in urls:
        if "/Repair/Refrigerator/" in url or "/Repair/Dishwasher/" in url:
            filtered.append(url)
    return filtered


# ── Step 2: Fetch HTML ────────────────────────────────────────────────────────

def fetch_page(url: str) -> tuple[str, str]:
    """
    Fetch URL, fall back to Wayback if needed.
    Returns (html, source) where source is 'direct' or 'wayback'.
    """
    html = None

    # Direct attempt
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200 and len(resp.text) >= MIN_CHARS:
            html = resp.text
            return html, "direct"
        else:
            print(f"  Direct returned {resp.status_code} or short body ({len(resp.text)} chars), trying Wayback...")
    except Exception as e:
        print(f"  Direct fetch failed ({e}), trying Wayback...")

    # Wayback fallback
    wayback_url = f"{WAYBACK_BASE}/{url}"
    try:
        resp = requests.get(wayback_url, headers=HEADERS, timeout=15)
        if resp.status_code == 200 and len(resp.text) >= MIN_CHARS:
            html = resp.text
            return html, "wayback"
        else:
            print(f"  Wayback returned {resp.status_code} or short body ({len(resp.text)} chars)")
    except Exception as e:
        print(f"  Wayback fetch failed ({e})")

    return "", "failed"


# ── Step 3: Parse repair page ─────────────────────────────────────────────────

PS_RE = re.compile(r"PS\d+")


def extract_appliance(url: str) -> str:
    """Extract 'refrigerator' or 'dishwasher' from URL."""
    if "/Repair/Refrigerator/" in url:
        return "refrigerator"
    if "/Repair/Dishwasher/" in url:
        return "dishwasher"
    return "unknown"


def extract_symptom(url: str) -> str:
    """
    Extract symptom from URL last path segment.
    e.g. .../Not-Cooling/ -> 'Not Cooling'
         .../Whirlpool/Not-Cooling/ -> 'Not Cooling'
    """
    parts = [p for p in url.rstrip("/").split("/") if p]
    if not parts:
        return ""
    segment = parts[-1]
    # If the last segment is a brand name (single word, title-case, no hyphens that look like a symptom)
    # and the one before looks like a symptom, we might be on a brand page — return segment anyway
    return segment.replace("-", " ")


def extract_brand(url: str) -> str:
    """
    For brand-specific pages like /Repair/Dishwasher/Whirlpool/Not-Draining/,
    extract the brand. Returns '' for generic pages.
    """
    parts = [p for p in url.rstrip("/").split("/") if p]
    # Structure: ..., Repair, Appliance, [Brand,] Symptom
    # Find index of appliance
    try:
        repair_idx = next(i for i, p in enumerate(parts) if p == "Repair")
        appliance_idx = repair_idx + 1
        # If there are 2+ path segments after appliance, middle one is brand
        after = parts[appliance_idx + 1:]
        if len(after) >= 2:
            return after[0]
    except StopIteration:
        pass
    return ""


def extract_parts_mentioned(soup: BeautifulSoup, html: str) -> list[str]:
    """Extract PS numbers from page — from link hrefs and text."""
    found = set()

    # From link hrefs: /PS12345-... pattern
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(r"/PS(\d+)", href)
        if m:
            found.add(f"PS{m.group(1)}")

    # From raw HTML text: PS\d+ patterns
    for match in PS_RE.finditer(html):
        found.add(match.group(0))

    return sorted(found)


def extract_causes(soup: BeautifulSoup) -> list[str]:
    """
    Extract cause headings from the repair page.
    Looks for h2/h3 near 'cause' text, or list items in cause sections.
    """
    causes = []

    # Strategy 1: headings that contain 'cause' context
    # Look for a section with id/class containing 'cause'
    cause_section = (
        soup.find(id=re.compile(r"cause", re.I))
        or soup.find(class_=re.compile(r"cause", re.I))
    )
    if cause_section:
        for el in cause_section.find_all(["h2", "h3", "h4", "li"]):
            text = el.get_text(strip=True)
            if text and len(text) > 5:
                causes.append(text)
        if causes:
            return causes[:20]

    # Strategy 2: h2/h3 headings that follow a "cause" heading
    in_causes = False
    for el in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = el.get_text(strip=True)
        if re.search(r"\bcause[s]?\b", text, re.I) and len(text) < 80:
            in_causes = True
            continue
        if in_causes:
            if el.name in ("h1", "h2") and not re.search(r"\bcause", text, re.I):
                break
            if text and len(text) > 5:
                causes.append(text)

    if causes:
        return causes[:20]

    # Strategy 3: look for divs/sections labeled with part names that could be causes
    # Many PartSelect repair pages list causes as card titles
    for el in soup.find_all(class_=re.compile(r"repair-story|cause|symptom-cause|js-repair", re.I)):
        title = el.find(["h2", "h3", "h4", "strong", "b"])
        if title:
            text = title.get_text(strip=True)
            if text and len(text) > 5:
                causes.append(text)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in causes:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    return unique[:20]


def extract_description(soup: BeautifulSoup) -> str:
    """Extract first 500 chars of meaningful body text."""
    # Remove script/style elements
    for tag in soup(["script", "style", "noscript", "header", "nav", "footer"]):
        tag.decompose()

    # Try specific containers first
    for selector_args in [
        {"class_": re.compile(r"repair-story|repair-content|main-content|page-content", re.I)},
        {"id": re.compile(r"main-content|content|repair", re.I)},
        {"class_": re.compile(r"description|intro|overview", re.I)},
    ]:
        el = soup.find(["div", "section", "article"], **selector_args)
        if el:
            text = el.get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > 100:
                return text[:500]

    # Fallback: main tag or body
    main = soup.find("main") or soup.find("body")
    if main:
        text = main.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:500]

    return ""


def extract_difficulty(soup: BeautifulSoup) -> str:
    """Extract repair difficulty if mentioned."""
    # Look for explicit difficulty mentions
    for pattern in [
        r"difficulty[:\s]+([A-Za-z ]+?)(?:\s+time|\s+repair|\s*[\.\|<\n])",
        r"repair\s+difficulty[:\s]+([A-Za-z ]+)",
    ]:
        m = re.search(pattern, soup.get_text(), re.I)
        if m:
            return m.group(1).strip()[:50]

    # Look in elements
    for el in soup.find_all(class_=re.compile(r"difficulty|repair.?level", re.I)):
        text = el.get_text(strip=True)
        if text and len(text) < 50:
            return text

    return ""


def parse_repair_page(html: str, url: str) -> dict:
    """Parse a repair guide HTML page into a structured dict."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove Wayback Machine toolbar noise
    wm_bar = soup.find(id="wm-ipp-inside")
    if wm_bar:
        wm_bar.decompose()

    appliance = extract_appliance(url)
    symptom   = extract_symptom(url)
    brand     = extract_brand(url)

    description     = extract_description(soup)
    causes          = extract_causes(soup)
    parts_mentioned = extract_parts_mentioned(soup, html)
    difficulty      = extract_difficulty(soup)

    result = {
        "url":             url,
        "appliance":       appliance,
        "symptom":         symptom,
        "description":     description,
        "causes":          causes,
        "parts_mentioned": parts_mentioned,
        "difficulty":      difficulty,
    }
    if brand:
        result["brand"] = brand

    return result


# ── Step 4: Build symptom_part_map from parts_raw.json ───────────────────────

def load_parts_symptoms(parts_json_path: Path) -> dict[str, list[str]]:
    """
    Load parts_raw.json and return {symptom_key: [PS numbers]} from part symptoms.
    symptom_key format: "{appliance}|{symptom text}"
    """
    if not parts_json_path.exists():
        print(f"  Warning: {parts_json_path} not found, skipping parts augmentation")
        return {}

    with parts_json_path.open(encoding="utf-8") as f:
        parts = json.load(f)

    symptom_map: dict[str, list[str]] = {}
    for part in parts:
        pn       = part.get("part_number", "")
        category = part.get("category", "")
        symptoms = part.get("symptoms", [])

        if not pn or not category or not symptoms:
            continue

        for symptom_text in symptoms:
            # Normalise: strip trailing punctuation, lowercase key prefix
            clean = symptom_text.strip().rstrip(".")
            key   = f"{category.lower()}|{clean}"
            if key not in symptom_map:
                symptom_map[key] = []
            if pn not in symptom_map[key]:
                symptom_map[key].append(pn)

    return symptom_map


# ── Step 5: Main ──────────────────────────────────────────────────────────────

def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Clean up old output files
    for old_file in ["repairs_raw.json", "repairs.json"]:
        old_path = DATA_DIR / old_file
        if old_path.exists():
            old_path.unlink()
            print(f"Deleted old {old_file}")

    # Parse sitemap
    print(f"\nParsing sitemap: {XML_PATH}")
    all_urls     = parse_sitemap(XML_PATH)
    filtered_urls = filter_urls(all_urls)
    print(f"Total URLs in sitemap:       {len(all_urls)}")
    print(f"Refrigerator+Dishwasher URLs:{len(filtered_urls)}")

    # Fetch and parse each page
    repairs      = []
    failed_urls  = []
    total        = len(filtered_urls)

    print(f"\nFetching {total} repair pages (1 req/sec)...\n")

    for i, url in enumerate(filtered_urls, 1):
        print(f"[{i:3d}/{total}] {url}")
        html, source = fetch_page(url)
        time.sleep(RATE_LIMIT)

        if not html:
            print(f"  SKIP: could not fetch {url}")
            failed_urls.append(url)
            continue

        try:
            repair = parse_repair_page(html, url)
            repair["_source"] = source
            repairs.append(repair)
            parts_count = len(repair["parts_mentioned"])
            causes_count = len(repair["causes"])
            print(f"  OK [{source}] symptom='{repair['symptom']}' parts={parts_count} causes={causes_count}")
        except Exception as e:
            print(f"  PARSE ERROR for {url}: {e}")
            failed_urls.append(url)

    print(f"\nFetched {len(repairs)} pages successfully, {len(failed_urls)} failed.")

    # Save repairs.json (remove internal _source field from final output)
    repairs_clean = []
    for r in repairs:
        entry = {k: v for k, v in r.items() if k != "_source"}
        repairs_clean.append(entry)

    OUT_REPAIRS.write_text(
        json.dumps(repairs_clean, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"Saved {len(repairs_clean)} repair guides -> {OUT_REPAIRS}")

    # Build symptom_part_map from scraped repairs
    symptom_map: dict[str, list[str]] = {}

    for repair in repairs:
        appliance = repair["appliance"]
        symptom   = repair["symptom"]
        parts     = repair["parts_mentioned"]

        if appliance == "unknown" or not symptom:
            continue

        key = f"{appliance}|{symptom}"
        if key not in symptom_map:
            symptom_map[key] = []
        for ps in parts:
            if ps not in symptom_map[key]:
                symptom_map[key].append(ps)

    # Augment with data from parts_raw.json
    print(f"\nAugmenting symptom_part_map from {PARTS_JSON}...")
    parts_symptoms = load_parts_symptoms(PARTS_JSON)
    augmented_keys = 0
    new_ps_added   = 0

    for key, ps_list in parts_symptoms.items():
        if key not in symptom_map:
            symptom_map[key] = []
            augmented_keys += 1
        for ps in ps_list:
            if ps not in symptom_map[key]:
                symptom_map[key].append(ps)
                new_ps_added += 1

    print(f"  Added {augmented_keys} new symptom keys from parts data")
    print(f"  Added {new_ps_added} new PS number references")

    OUT_MAP.write_text(
        json.dumps(symptom_map, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"Saved {len(symptom_map)} symptom keys -> {OUT_MAP}")

    # Summary stats
    total_parts_linked = sum(len(v) for v in symptom_map.values())
    unique_ps = set(ps for v in symptom_map.values() for ps in v)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Repair pages fetched:        {len(repairs)}")
    print(f"  Direct:                    {sum(1 for r in repairs if r.get('_source') == 'direct')}")
    print(f"  Wayback:                   {sum(1 for r in repairs if r.get('_source') == 'wayback')}")
    print(f"Failed pages:                {len(failed_urls)}")
    print(f"Total symptom keys:          {len(symptom_map)}")
    print(f"Unique PS numbers linked:    {len(unique_ps)}")
    print(f"Total part references:       {total_parts_linked}")

    # Top 5 symptoms by part count
    top5 = sorted(symptom_map.items(), key=lambda x: len(x[1]), reverse=True)[:5]
    print("\nTop 5 symptoms by part count:")
    for key, ps_list in top5:
        print(f"  {key!r:50s}  {len(ps_list)} parts")

    if failed_urls:
        print(f"\nFailed URLs ({len(failed_urls)}):")
        for u in failed_urls:
            print(f"  {u}")

    print("\nDone.")


if __name__ == "__main__":
    main()
