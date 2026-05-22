"""
Blog scraper for PartSelect.com
Reads blog URLs from XML sitemap, fetches each page, extracts metadata,
and writes 3 JSON output files.
"""

import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
import re
import json
import time
import os

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR      = r"C:/Users/aditi/partselect-agent"
XML_PATH      = os.path.join(BASE_DIR, "xml", "PartSelect.com_Sitemap_Blogs.xml")
DATA_DIR      = os.path.join(BASE_DIR, "scraper", "data")
BLOGS_JSON    = os.path.join(DATA_DIR, "blogs.json")
BLOG_PART_MAP = os.path.join(DATA_DIR, "blog_part_map.json")
TOPIC_PART_MAP= os.path.join(DATA_DIR, "topic_part_map.json")
LEGACY_RAW    = os.path.join(DATA_DIR, "blogs_raw.json")

os.makedirs(DATA_DIR, exist_ok=True)

# Remove legacy file if present
if os.path.exists(LEGACY_RAW):
    os.remove(LEGACY_RAW)
    print(f"Deleted legacy file: {LEGACY_RAW}")

# ── Constants ──────────────────────────────────────────────────────────────────
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
SLEEP_BETWEEN = 0.8
SYMPTOM_KWS = [
    "not cooling", "not draining", "ice maker", "leaking", "won't start",
    "not cleaning", "water filter", "not freezing", "door seal", "noisy"
]
PS_PATTERN = re.compile(r'PS\d{5,8}', re.IGNORECASE)

# ── Step 1 – Parse sitemap XML ─────────────────────────────────────────────────
tree = ET.parse(XML_PATH)
root = tree.getroot()
ns   = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns)]
print(f"Found {len(urls)} blog URLs in sitemap.")

# ── Helper: fetch with Wayback fallback ───────────────────────────────────────
def fetch_page(url):
    """Return (html_text, final_url) or (None, url) on total failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200 and len(r.text) >= 500:
            return r.text, url
    except Exception as e:
        print(f"  Primary fetch error for {url}: {e}")

    # Wayback fallback
    wb_url = f"https://web.archive.org/web/2023/{url}"
    try:
        r2 = requests.get(wb_url, headers=HEADERS, timeout=15)
        if r2.status_code == 200 and len(r2.text) >= 500:
            return r2.text, wb_url
    except Exception as e:
        print(f"  Wayback fetch error for {url}: {e}")

    return None, url

# ── Helper: determine appliance type ─────────────────────────────────────────
def get_appliance(text_lower):
    has_ref = any(kw in text_lower for kw in ["refrigerator", "fridge", "ice maker"])
    has_dw  = "dishwasher" in text_lower
    if has_ref and has_dw:
        return "both"
    if has_ref:
        return "refrigerator"
    if has_dw:
        return "dishwasher"
    return "general"

# ── Helper: extract body text ─────────────────────────────────────────────────
def get_body_text(soup):
    """Try article/main first, then fall back to body."""
    for selector in ["article", "main", '[class*="content"]', '[class*="blog"]', "body"]:
        tag = soup.select_one(selector)
        if tag:
            text = tag.get_text(separator=" ", strip=True)
            if len(text) > 200:
                return text
    return soup.get_text(separator=" ", strip=True)

# ── Main scraping loop ─────────────────────────────────────────────────────────
results = []
total   = len(urls)

for idx, url in enumerate(urls, 1):
    print(f"[{idx}/{total}] {url}")

    html, fetched_from = fetch_page(url)

    if html is None:
        print(f"  FAILED – skipping")
        results.append({
            "url": url,
            "title": "",
            "appliance": "general",
            "summary": "",
            "parts_mentioned": [],
            "symptom_keywords": []
        })
        time.sleep(SLEEP_BETWEEN)
        continue

    soup = BeautifulSoup(html, "html.parser")

    # Title
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title:
        t = soup.find("title")
        title = t.get_text(strip=True) if t else ""

    # Body text
    body_text = get_body_text(soup)
    text_lower = body_text.lower()

    # Appliance
    appliance = get_appliance(text_lower)

    # Summary (first 300 chars of body)
    summary = body_text[:300]

    # PS part numbers from entire HTML (not just visible text)
    raw_html = html
    ps_raw   = PS_PATTERN.findall(raw_html)
    # Normalise to PS{digits} with uppercase prefix, deduplicate preserving order
    seen = {}
    for p in ps_raw:
        normed = "PS" + p[2:]   # keep digits as-is, force PS prefix uppercase
        seen[normed] = True
    parts_mentioned = list(seen.keys())

    # Symptom keywords
    symptom_keywords = [kw for kw in SYMPTOM_KWS if kw.lower() in text_lower]

    results.append({
        "url": url,
        "title": title,
        "appliance": appliance,
        "summary": summary,
        "parts_mentioned": parts_mentioned,
        "symptom_keywords": symptom_keywords
    })

    time.sleep(SLEEP_BETWEEN)

# ── Write blogs.json ───────────────────────────────────────────────────────────
with open(BLOGS_JSON, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nWrote {BLOGS_JSON}")

# ── Write blog_part_map.json ───────────────────────────────────────────────────
blog_part_map = {
    r["url"]: r["parts_mentioned"]
    for r in results
    if r["parts_mentioned"]
}
with open(BLOG_PART_MAP, "w", encoding="utf-8") as f:
    json.dump(blog_part_map, f, indent=2, ensure_ascii=False)
print(f"Wrote {BLOG_PART_MAP}")

# ── Write topic_part_map.json ──────────────────────────────────────────────────
topic_part_map = {kw: [] for kw in SYMPTOM_KWS}
seen_per_topic = {kw: set() for kw in SYMPTOM_KWS}

for r in results:
    for kw in r["symptom_keywords"]:
        for p in r["parts_mentioned"]:
            if p not in seen_per_topic[kw]:
                seen_per_topic[kw].add(p)
                topic_part_map[kw].append(p)

# Remove keywords with no parts
topic_part_map = {k: v for k, v in topic_part_map.items() if v}

with open(TOPIC_PART_MAP, "w", encoding="utf-8") as f:
    json.dump(topic_part_map, f, indent=2, ensure_ascii=False)
print(f"Wrote {TOPIC_PART_MAP}")

# ── Summary ────────────────────────────────────────────────────────────────────
fetched_ok   = sum(1 for r in results if r["title"] or r["summary"])
had_parts    = sum(1 for r in results if r["parts_mentioned"])
appliance_ct = {}
for r in results:
    appliance_ct[r["appliance"]] = appliance_ct.get(r["appliance"], 0) + 1

print("\n=== SUMMARY ===")
print(f"Total blog URLs:    {total}")
print(f"Successfully fetched: {fetched_ok}")
print(f"Blogs with parts:   {had_parts}")
print("Appliance breakdown:")
for k, v in sorted(appliance_ct.items()):
    print(f"  {k}: {v}")
