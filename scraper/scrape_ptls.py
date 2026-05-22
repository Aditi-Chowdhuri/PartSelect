"""
PTL (Part Type Landing) database builder.
Reads PTLs XML → extracts brand/appliance/part_type metadata from URLs,
cross-references with sitemap_parts.json to assign parts,
and attempts direct scraping for top 50 pages.

Outputs:
  data/ptls.json
  data/part_type_map.json
  data/brand_part_type_index.json
"""
import json, re, time, xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
import requests
from bs4 import BeautifulSoup

XML_FILE    = Path("../xml/PartSelect.com_Sitemap_PTLs.xml")
SITEMAP     = Path("data/sitemap_parts.json")
OUT_DIR     = Path("data")
HEADERS     = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Brands to prioritise for live scraping (by market share)
PRIORITY_BRANDS = {"whirlpool", "ge", "frigidaire", "samsung", "lg", "bosch",
                   "kitchenaid", "maytag", "electrolux", "amana"}
PRIORITY_TYPES  = {"ice makers", "water filters", "spray arms", "drain pumps",
                   "door gaskets", "control boards", "water inlet valves",
                   "evaporator fans", "defrost heaters", "dish racks"}

def parse_locs(path):
    locs = []
    for _, elem in ET.iterparse(str(path), events=("end",)):
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "loc" and elem.text:
            locs.append(elem.text.strip())
        elem.clear()
    return locs

def parse_ptl_url(url):
    """Extract (brand, appliance, part_type) from PTL URL or return (None,None,None)."""
    m = re.search(r"/([^/]+)-(Refrigerator|Dishwasher)-(.+?)\.htm$", url, re.I)
    if not m:
        return None, None, None
    brand     = m.group(1)
    appliance = m.group(2).lower()
    part_type = m.group(3).replace("-", " ")
    return brand, appliance, part_type

def keywords_from_part_type(part_type):
    """Split part_type into search words, remove noise words."""
    noise = {"and", "or", "the", "a", "an", "of", "for", "with"}
    words = [w.lower() for w in part_type.split() if w.lower() not in noise and len(w) > 1]
    return words

def slug_matches_part_type(url_slug, keywords):
    """Return True if all keywords appear in the url slug (case-insensitive)."""
    slug_lower = url_slug.lower().replace("-", " ")
    return all(kw in slug_lower for kw in keywords)

def build_ptl_entries(locs, sitemap):
    """Phase 1+2: metadata extraction + sitemap cross-reference."""
    # Index sitemap by (brand_upper, category) -> list of (ps_num, url_slug)
    brand_cat_parts = defaultdict(list)
    for entry in sitemap:
        b = entry.get("brand", "").upper()
        c = entry.get("category", "")
        ps = entry.get("ps_num", "")
        url = entry.get("url", "")
        slug = url.rsplit("/", 1)[-1].replace(".htm", "").replace("-", " ")
        if b and c and ps:
            brand_cat_parts[(b, c)].append((ps, slug))

    entries = []
    seen = set()
    for url in locs:
        if url in seen:
            continue
        brand, appliance, part_type = parse_ptl_url(url)
        if not brand:
            continue
        seen.add(url)
        keywords = keywords_from_part_type(part_type)
        # Find matching parts from sitemap
        candidates = brand_cat_parts.get((brand.upper(), appliance), [])
        matched = [f"PS{ps}" for ps, slug in candidates if slug_matches_part_type(slug, keywords)]
        entries.append({
            "url":           url,
            "brand":         brand,
            "appliance":     appliance,
            "part_type":     part_type,
            "parts_ps_nums": matched,
        })
    return entries

def scrape_top_pages(entries, max_pages=50):
    """Phase 3: direct scrape the most important PTL pages to supplement parts."""
    # Score entries: priority brand + priority type + few existing parts = scrape first
    def score(e):
        b = int(e["brand"].lower() in PRIORITY_BRANDS) * 2
        t = int(e["part_type"].lower() in PRIORITY_TYPES) * 2
        # Prefer entries with few or no cross-ref parts (more to gain)
        gap = int(len(e["parts_ps_nums"]) < 3)
        return b + t + gap

    candidates = sorted(entries, key=score, reverse=True)[:max_pages]
    print(f"\nPhase 3: direct scraping top {len(candidates)} PTL pages...")

    for i, entry in enumerate(candidates):
        try:
            r = requests.get(entry["url"], headers=HEADERS, timeout=12)
            if r.status_code == 200:
                new_ps = list(dict.fromkeys(
                    f"PS{m}" for m in re.findall(r"/PS(\d+)-", r.text)
                ))
                added = [ps for ps in new_ps if ps not in entry["parts_ps_nums"]]
                entry["parts_ps_nums"] = list(dict.fromkeys(entry["parts_ps_nums"] + new_ps))
                print(f"  [{i+1}/{len(candidates)}] {entry['brand']} {entry['part_type']}: "
                      f"+{len(added)} new PS nums (total {len(entry['parts_ps_nums'])})")
            else:
                print(f"  [{i+1}/{len(candidates)}] {entry['brand']} {entry['part_type']}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  [{i+1}/{len(candidates)}] FAIL {entry['url']}: {e}")
        time.sleep(0.8)
    return entries

def main():
    OUT_DIR.mkdir(exist_ok=True)

    # Load
    locs    = parse_locs(XML_FILE)
    sitemap = json.loads(SITEMAP.read_text(encoding="utf-8")) if SITEMAP.exists() else []
    print(f"PTL XML: {len(locs)} total URLs")
    print(f"Sitemap: {len(sitemap)} classified parts")

    # Phase 1+2
    entries = build_ptl_entries(locs, sitemap)
    fridge_n = sum(1 for e in entries if e["appliance"] == "refrigerator")
    dish_n   = sum(1 for e in entries if e["appliance"] == "dishwasher")
    with_parts = sum(1 for e in entries if e["parts_ps_nums"])
    print(f"PTL entries: {len(entries)} ({fridge_n} fridge, {dish_n} dish)")
    print(f"With cross-ref parts (pre-scrape): {with_parts}")

    # Phase 3
    entries = scrape_top_pages(entries)

    # Only save entries that have at least 1 part
    final = [e for e in entries if e["parts_ps_nums"]]
    print(f"\nFinal PTL entries with parts: {len(final)}")

    (OUT_DIR / "ptls.json").write_text(
        json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved -> data/ptls.json")

    # part_type_map: appliance|part_type -> {brands[], parts[]}
    ptm = defaultdict(lambda: {"brands": [], "parts": []})
    for e in final:
        key = f"{e['appliance']}|{e['part_type']}"
        if e["brand"] not in ptm[key]["brands"]:
            ptm[key]["brands"].append(e["brand"])
        for ps in e["parts_ps_nums"]:
            if ps not in ptm[key]["parts"]:
                ptm[key]["parts"].append(ps)

    (OUT_DIR / "part_type_map.json").write_text(
        json.dumps(dict(ptm), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(ptm)} part_type keys -> data/part_type_map.json")

    # brand_part_type_index: brand -> appliance -> part_type -> count
    bpti = defaultdict(lambda: defaultdict(dict))
    for e in final:
        bpti[e["brand"]][e["appliance"]][e["part_type"]] = len(e["parts_ps_nums"])

    (OUT_DIR / "brand_part_type_index.json").write_text(
        json.dumps({b: dict(apps) for b, apps in bpti.items()}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"Saved {len(bpti)} brands -> data/brand_part_type_index.json")

    # Summary
    top10 = sorted(ptm.items(), key=lambda x: -len(x[1]["parts"]))[:10]
    print("\nTop 10 part types by part count:")
    for key, val in top10:
        print(f"  {key:45s}  {len(val['parts']):4d} parts  {len(val['brands'])} brands")

    print("\nDone.")

if __name__ == "__main__":
    main()
