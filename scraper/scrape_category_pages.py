"""
Scrape PartSelect CategoryPages XML → category_pages.json + brand_appliance_map.json
"""
import json, re, time, xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
import requests
from bs4 import BeautifulSoup

XML_FILE  = Path("../xml/PartSelect.com_Sitemap_CategoryPages.xml")
SITEMAP   = Path("data/sitemap_parts.json")
OUT_DIR   = Path("data")
HEADERS   = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def parse_locs(path):
    locs = []
    for _, elem in ET.iterparse(str(path), events=("end",)):
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "loc" and elem.text:
            locs.append(elem.text.strip())
        elem.clear()
    return locs

def classify_cat_url(url):
    """Return (brand, appliance) or (None, None) if not fridge/dish."""
    m = re.search(r"/([^/]+)-(Refrigerator|Dishwasher)-Parts\.htm$", url, re.I)
    if not m:
        return None, None
    return m.group(1), m.group(2).lower()

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200 and len(r.text) > 500:
            return r.text
    except Exception:
        pass
    # Wayback fallback
    try:
        wb = f"https://web.archive.org/web/2023/{url}"
        r2 = requests.get(wb, headers=HEADERS, timeout=20)
        if r2.status_code == 200:
            return r2.text
    except Exception:
        pass
    return None

def extract_page(html, url, brand, appliance):
    soup = BeautifulSoup(html, "html.parser")
    ps_nums = list(dict.fromkeys(
        f"PS{m}" for m in re.findall(r"/PS(\d+)-", html)
    ))
    model_nums = list(dict.fromkeys(
        m.group(1) for m in (re.search(r"/Models/([^/?#]+)/?", a.get("href", ""))
                              for a in soup.find_all("a", href=True))
        if m
    ))
    # Part type headings
    part_types = []
    for tag in soup.find_all(["h2", "h3", "h4"]):
        t = tag.get_text(strip=True)
        if 3 < len(t) < 60 and not any(kw in t.lower() for kw in ["skip", "close", "menu", "sign"]):
            part_types.append(t)
    return {
        "url": url,
        "brand": brand,
        "appliance": appliance,
        "parts_ps_nums": ps_nums[:50],
        "model_numbers": model_nums[:30],
        "part_types_available": part_types[:20],
    }

def main():
    OUT_DIR.mkdir(exist_ok=True)

    # Parse and filter XML
    locs = parse_locs(XML_FILE)
    seen, filtered = set(), []
    for url in locs:
        brand, appliance = classify_cat_url(url)
        if brand and appliance and url not in seen:
            seen.add(url)
            filtered.append((url, brand, appliance))
    print(f"Category pages: {len(locs)} total -> {len(filtered)} fridge/dish unique")

    # Scrape
    results = []
    for i, (url, brand, appliance) in enumerate(filtered):
        html = fetch(url)
        if html:
            rec = extract_page(html, url, brand, appliance)
            results.append(rec)
            print(f"  [{i+1}/{len(filtered)}] {brand} {appliance}: "
                  f"{len(rec['parts_ps_nums'])} parts, {len(rec['model_numbers'])} models")
        else:
            results.append({"url": url, "brand": brand, "appliance": appliance,
                             "parts_ps_nums": [], "model_numbers": [], "part_types_available": []})
            print(f"  [{i+1}/{len(filtered)}] MISS {url}")
        time.sleep(0.8)

    # Save category_pages.json
    (OUT_DIR / "category_pages.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(results)} entries -> data/category_pages.json")

    # Build brand_appliance_map from scrape results
    bam = defaultdict(lambda: {"parts": [], "models": [], "part_types": []})
    for rec in results:
        key = f"{rec['brand']}|{rec['appliance']}"
        bam[key]["parts"]      = list(dict.fromkeys(bam[key]["parts"]      + rec["parts_ps_nums"]))
        bam[key]["models"]     = list(dict.fromkeys(bam[key]["models"]     + rec["model_numbers"]))
        bam[key]["part_types"] = list(dict.fromkeys(bam[key]["part_types"] + rec["part_types_available"]))

    # Augment from sitemap_parts.json
    if SITEMAP.exists():
        sitemap = json.loads(SITEMAP.read_text(encoding="utf-8"))
        aug = 0
        for entry in sitemap:
            brand = entry.get("brand", "")
            cat   = entry.get("category", "")
            ps    = f"PS{entry.get('ps_num', '')}"
            if not brand or not cat or not ps:
                continue
            key = f"{brand}|{cat}"
            if ps not in bam[key]["parts"]:
                bam[key]["parts"].append(ps)
                aug += 1
        print(f"Augmented brand_appliance_map with {aug} parts from sitemap_parts.json")

    (OUT_DIR / "brand_appliance_map.json").write_text(
        json.dumps(dict(bam), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(bam)} brand|appliance keys -> data/brand_appliance_map.json")

    # Summary
    fridge = sum(1 for r in results if r["appliance"] == "refrigerator")
    dish   = sum(1 for r in results if r["appliance"] == "dishwasher")
    w_parts = sum(1 for r in results if r["parts_ps_nums"])
    print(f"\nSummary: {fridge} fridge pages, {dish} dish pages, {w_parts} with scraped parts")

if __name__ == "__main__":
    main()
