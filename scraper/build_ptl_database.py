#!/usr/bin/env python3
"""
PTL (Part Type Landing) Database Builder for PartSelect
Phases:
  1. Parse XML sitemap, extract PTL metadata for fridge/dishwasher
  2. Cross-reference with sitemap_parts.json to find matching PS numbers
  3. Attempt direct scraping of top 30 PTL pages
Output: ptls.json, part_type_map.json, brand_part_type_index.json
"""

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import requests

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path("C:/Users/aditi/partselect-agent")
XML_PATH = BASE_DIR / "xml" / "PartSelect.com_Sitemap_PTLs.xml"
PARTS_JSON = BASE_DIR / "scraper" / "data" / "sitemap_parts.json"
OUT_DIR = BASE_DIR / "scraper" / "data"

OUT_PTLS = OUT_DIR / "ptls.json"
OUT_PART_TYPE_MAP = OUT_DIR / "part_type_map.json"
OUT_BRAND_INDEX = OUT_DIR / "brand_part_type_index.json"

# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_ptl_meta(url: str) -> dict | None:
    """
    Given a PTL URL like:
      https://www.partselect.com/Whirlpool-Refrigerator-Ice-Makers.htm
    Return {url, brand, appliance, part_type} or None if not a fridge/dish URL.
    """
    path = url.rstrip("/")
    filename = path.split("/")[-1]           # Whirlpool-Refrigerator-Ice-Makers.htm
    stem = filename.replace(".htm", "")      # Whirlpool-Refrigerator-Ice-Makers

    # Case-insensitive search for -Refrigerator- or -Dishwasher-
    m = re.search(r"^(.+?)-(Refrigerator|Dishwasher)-(.+)$", stem, re.IGNORECASE)
    if not m:
        return None

    brand = m.group(1)                               # Whirlpool
    appliance = m.group(2).lower()                   # refrigerator
    part_type_slug = m.group(3)                      # Ice-Makers
    part_type = part_type_slug.replace("-", " ")     # Ice Makers

    return {
        "url": url,
        "brand": brand,
        "appliance": appliance,
        "part_type": part_type,
        "parts_ps_nums": []
    }


def slug_from_url(part_url: str) -> str:
    """
    Extract the slug portion from a part URL for keyword matching.
    e.g. /PS258088-GE-WD01X10065-CLAMP-HOSE.htm  → 'ps258088 ge wd01x10065 clamp hose'
    """
    filename = part_url.rstrip("/").split("/")[-1].replace(".htm", "")
    return filename.replace("-", " ").lower()


def keywords_from_part_type(part_type: str) -> list[str]:
    """
    Split part_type into significant keywords (1+ chars, skip stopwords).
    'Ice Makers'   → ['ice', 'maker']  (singularize common plurals)
    'Spray Arms'   → ['spray', 'arm']
    'Door Gaskets' → ['door', 'gasket']
    """
    stopwords = {"and", "or", "the", "a", "an", "of", "for", "with"}
    words = part_type.lower().split()

    result = []
    for w in words:
        if w in stopwords:
            continue
        # Simple singularization: strip trailing 's' for common plurals
        # but keep words like 'glass', 'brass', 'ress' intact
        singular = w
        if w.endswith("ies") and len(w) > 4:
            singular = w[:-3] + "y"          # e.g. batteries → battery
        elif w.endswith("ses") and len(w) > 4:
            singular = w[:-2]                 # glasses → glass (keep both)
        elif w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
            singular = w[:-1]                 # makers → maker
        result.append(singular)

    return result


def part_matches_ptl(part: dict, brand: str, appliance: str, keywords: list[str]) -> bool:
    """Return True if a part record matches this PTL's brand/appliance/keywords."""
    # Brand match (case-insensitive)
    if part.get("brand", "").lower() != brand.lower():
        return False
    # Category / appliance match
    if part.get("category", "").lower() != appliance.lower():
        return False
    # Keyword match against URL slug
    slug = slug_from_url(part.get("url", ""))
    return all(kw in slug for kw in keywords)


# ── Phase 1: Parse XML ─────────────────────────────────────────────────────────

def phase1_parse_xml() -> list[dict]:
    print("=" * 60)
    print("PHASE 1: Parsing PTL XML sitemap…")
    tree = ET.parse(XML_PATH)
    root = tree.getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    all_locs = [
        url.find("sm:loc", ns).text.strip()
        for url in root.findall("sm:url", ns)
        if url.find("sm:loc", ns) is not None
    ]
    print(f"  Total PTL URLs in XML: {len(all_locs)}")

    seen_urls: set[str] = set()
    entries: list[dict] = []
    skipped_dup = 0

    for url in all_locs:
        meta = extract_ptl_meta(url)
        if meta is None:
            continue
        if url in seen_urls:
            skipped_dup += 1
            continue
        seen_urls.add(url)
        entries.append(meta)

    print(f"  Fridge/Dishwasher PTLs (deduplicated): {len(entries)}")
    if skipped_dup:
        print(f"  Skipped duplicates: {skipped_dup}")

    return entries


# ── Phase 2: Cross-reference with sitemap_parts.json ──────────────────────────

def phase2_crossref(entries: list[dict]) -> list[dict]:
    print("=" * 60)
    print("PHASE 2: Cross-referencing with sitemap_parts.json…")

    with open(PARTS_JSON, encoding="utf-8") as f:
        parts = json.load(f)
    print(f"  Loaded {len(parts):,} parts from sitemap_parts.json")

    # Build lookup index: (brand_lower, category_lower) → list of parts
    brand_cat_index: dict[tuple, list] = defaultdict(list)
    for p in parts:
        key = (p.get("brand", "").lower(), p.get("category", "").lower())
        brand_cat_index[key].append(p)

    matched_count = 0

    for entry in entries:
        brand = entry["brand"]
        appliance = entry["appliance"]
        part_type = entry["part_type"]

        keywords = keywords_from_part_type(part_type)
        if not keywords:
            continue

        candidate_parts = brand_cat_index.get((brand.lower(), appliance.lower()), [])

        ps_nums = []
        for p in candidate_parts:
            slug = slug_from_url(p.get("url", ""))
            if all(kw in slug for kw in keywords):
                ps_num = p.get("ps_num", "")
                if ps_num:
                    ps_nums.append(f"PS{ps_num}")

        entry["parts_ps_nums"] = ps_nums
        if ps_nums:
            matched_count += 1

    print(f"  PTL entries with ≥1 matched part: {matched_count}/{len(entries)}")
    return entries


# ── Phase 3: Attempted direct scraping ────────────────────────────────────────

# Top brands and part types to scrape
TOP_BRANDS = {"Whirlpool", "GE", "Frigidaire", "Samsung", "LG"}
TOP_PART_TYPES = {"Ice Makers", "Water Filters", "Door Gaskets", "Spray Arms", "Drain Pumps"}
PS_PATTERN = re.compile(r"/PS(\d+)-")


def select_scrape_targets(entries: list[dict], n: int = 30) -> list[dict]:
    """Pick up to n entries covering top brands × top part types."""
    priority: list[dict] = []
    seen_combos: set[tuple] = set()

    # First pass: top brand AND top part type
    for e in entries:
        if e["brand"] in TOP_BRANDS and e["part_type"] in TOP_PART_TYPES:
            combo = (e["brand"], e["appliance"], e["part_type"])
            if combo not in seen_combos:
                priority.append(e)
                seen_combos.add(combo)

    # Second pass: top brand only
    for e in entries:
        if len(priority) >= n:
            break
        if e["brand"] in TOP_BRANDS:
            combo = (e["brand"], e["appliance"], e["part_type"])
            if combo not in seen_combos:
                priority.append(e)
                seen_combos.add(combo)

    return priority[:n]


def phase3_scrape(entries: list[dict]) -> int:
    print("=" * 60)
    print("PHASE 3: Attempting direct scraping of top 30 PTL pages…")

    targets = select_scrape_targets(entries, 30)
    print(f"  Selected {len(targets)} PTL pages to scrape")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    # Build a fast lookup: url → entry
    url_to_entry = {e["url"]: e for e in entries}

    new_ps_total = 0

    for i, target in enumerate(targets):
        url = target["url"]
        print(f"  [{i+1:2d}/{len(targets)}] {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"         HTTP {resp.status_code} — skipping")
                time.sleep(1)
                continue

            html = resp.text
            found_nums = set(PS_PATTERN.findall(html))
            if found_nums:
                entry = url_to_entry[url]
                existing = set(entry["parts_ps_nums"])
                new_ones = {f"PS{n}" for n in found_nums} - existing
                entry["parts_ps_nums"] = sorted(existing | {f"PS{n}" for n in found_nums})
                new_ps_total += len(new_ones)
                print(f"         Found {len(found_nums)} PS nums ({len(new_ones)} new)")
            else:
                print(f"         0 PS hrefs visible (JS-rendered)")

        except requests.RequestException as exc:
            print(f"         Error: {exc}")

        time.sleep(1)

    print(f"  Net new PS numbers added via scraping: {new_ps_total}")
    return new_ps_total


# ── Output writers ─────────────────────────────────────────────────────────────

def build_part_type_map(entries: list[dict]) -> dict:
    """
    {
      "refrigerator|Ice Makers": {
        "brands": [...],
        "parts": [...]
      }
    }
    """
    pt_map: dict[str, dict] = {}
    for e in entries:
        if not e["parts_ps_nums"]:
            continue
        key = f"{e['appliance']}|{e['part_type']}"
        if key not in pt_map:
            pt_map[key] = {"brands": [], "parts": []}
        if e["brand"] not in pt_map[key]["brands"]:
            pt_map[key]["brands"].append(e["brand"])
        for ps in e["parts_ps_nums"]:
            if ps not in pt_map[key]["parts"]:
                pt_map[key]["parts"].append(ps)

    # Sort brands and parts within each entry
    for v in pt_map.values():
        v["brands"] = sorted(v["brands"])
        v["parts"] = sorted(v["parts"])

    return dict(sorted(pt_map.items()))


def build_brand_index(entries: list[dict]) -> dict:
    """
    {
      "Whirlpool": {
        "refrigerator": { "Ice Makers": 12, ... },
        "dishwasher":   { "Spray Arms": 4, ... }
      }
    }
    """
    index: dict[str, dict] = {}
    for e in entries:
        if not e["parts_ps_nums"]:
            continue
        brand = e["brand"]
        appliance = e["appliance"]
        part_type = e["part_type"]
        count = len(e["parts_ps_nums"])

        if brand not in index:
            index[brand] = {}
        if appliance not in index[brand]:
            index[brand][appliance] = {}
        index[brand][appliance][part_type] = (
            index[brand][appliance].get(part_type, 0) + count
        )

    # Sort alphabetically
    return {
        brand: {
            appl: dict(sorted(pt_counts.items()))
            for appl, pt_counts in sorted(appl_map.items())
        }
        for brand, appl_map in sorted(index.items())
    }


def write_outputs(entries: list[dict]) -> None:
    print("=" * 60)
    print("Writing output files…")

    # ptls.json — only entries with ≥1 matched part
    ptl_out = [e for e in entries if e["parts_ps_nums"]]
    if OUT_PTLS.exists():
        OUT_PTLS.unlink()
        print(f"  Deleted existing {OUT_PTLS.name}")
    with open(OUT_PTLS, "w", encoding="utf-8") as f:
        json.dump(ptl_out, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {OUT_PTLS.name}: {len(ptl_out)} entries")

    # part_type_map.json
    pt_map = build_part_type_map(entries)
    with open(OUT_PART_TYPE_MAP, "w", encoding="utf-8") as f:
        json.dump(pt_map, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {OUT_PART_TYPE_MAP.name}: {len(pt_map)} part-type keys")

    # brand_part_type_index.json
    brand_index = build_brand_index(entries)
    with open(OUT_BRAND_INDEX, "w", encoding="utf-8") as f:
        json.dump(brand_index, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {OUT_BRAND_INDEX.name}: {len(brand_index)} brands")


# ── Summary ────────────────────────────────────────────────────────────────────

def print_summary(entries: list[dict]) -> None:
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    with_parts = [e for e in entries if e["parts_ps_nums"]]
    brands = sorted({e["brand"] for e in entries})
    brands_with_parts = sorted({e["brand"] for e in with_parts})

    print(f"  Total PTL entries (fridge/dish):  {len(entries)}")
    print(f"  Entries with ≥1 matched part:     {len(with_parts)}")
    print(f"  Unique brands in PTL set:          {len(brands)}")
    print(f"  Unique brands with matched parts:  {len(brands_with_parts)}")

    # Top 10 part types by total part count
    pt_counts: dict[str, int] = defaultdict(int)
    for e in with_parts:
        key = f"{e['appliance']}|{e['part_type']}"
        pt_counts[key] += len(e["parts_ps_nums"])

    top10 = sorted(pt_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    print("\n  Top 10 part types by part count:")
    for rank, (pt, cnt) in enumerate(top10, 1):
        print(f"    {rank:2d}. {pt:<45s}  {cnt:4d} parts")

    # Breakdown by appliance
    fridges = [e for e in entries if e["appliance"] == "refrigerator"]
    dishes = [e for e in entries if e["appliance"] == "dishwasher"]
    print(f"\n  Refrigerator PTLs: {len(fridges)}  (with parts: {sum(1 for e in fridges if e['parts_ps_nums'])})")
    print(f"  Dishwasher PTLs:   {len(dishes)}  (with parts: {sum(1 for e in dishes if e['parts_ps_nums'])})")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("PartSelect PTL Database Builder")
    print("=" * 60)

    entries = phase1_parse_xml()
    entries = phase2_crossref(entries)
    phase3_scrape(entries)
    write_outputs(entries)
    print_summary(entries)

    print("=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
