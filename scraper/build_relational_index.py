"""
build_relational_index.py
Consolidates all scraped data into a unified relational index.

Inputs (all in data/):
  parts_raw.json           - scraped parts with names, symptoms, models
  sitemap_parts.json       - all 15,857 classified parts
  repairs.json             - 123 repair guides
  blogs.json               - blog articles (optional, if exists)
  category_pages.json      - 72 brand category pages
  ptls.json                - 63 part type landing pages
  brand_appliance_map.json - brand x appliance -> parts
  model_part_map.json      - model -> PS nums (existing)

Outputs (all in data/):
  symptom_part_map.json    - rebuilt from actual part symptom strings
  part_type_map.json       - rebuilt from part names + PTL data
  model_part_map.json      - enriched with parts_raw.json compatible_models
  blog_part_map.json       - blog url -> PS nums (if blogs.json exists)
  relational_summary.json  - stats overview for inspector
"""
import json, re
from pathlib import Path
from collections import defaultdict

DATA = Path("data")


def load(name):
    p = DATA / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def normalize_symptom(s):
    """Normalize symptom string for matching."""
    s = s.lower().strip().rstrip(".").strip()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


# ── Part-type keywords: map PTL part_type names to name keywords ──────────────
# These are used to classify scraped parts by part_type from their names.
_PART_TYPE_KEYWORDS = {
    "ice makers":             ["ice maker"],
    "water filters":          ["water filter"],
    "spray arms":             ["spray arm"],
    "drain pumps":            ["drain pump"],
    "door gaskets":           ["door gasket", "door seal"],
    "control boards":         ["control board", "main board", "pcb"],
    "water inlet valves":     ["water inlet valve", "inlet valve"],
    "evaporator fans":        ["evaporator fan"],
    "defrost heaters":        ["defrost heater"],
    "dish racks":             ["dish rack", "dishrack", "lower rack", "upper rack",
                               "silverware basket", "utensil basket"],
    "shelves":                ["shelf", "glass shelf", "door shelf"],
    "crisper drawers":        ["crisper drawer", "crisper pan", "deli drawer"],
    "door bins":              ["door bin", "door shelf"],
    "thermostats":            ["thermostat", "defrost thermostat"],
    "motors":                 ["motor", "drive motor"],
    "pumps":                  ["pump", "circulation pump", "wash pump"],
    "valves":                 ["valve"],
    "switches":               ["switch", "door switch"],
    "handles":                ["handle"],
    "hinges":                 ["hinge"],
    "seals and gaskets":      ["seal", "gasket", "o-ring"],
    "filters":                ["filter"],
    "fans and blowers":       ["fan", "blower"],
    "dispensers":             ["dispenser", "detergent dispenser", "rinse aid"],
    "doors":                  ["door"],
    "drawers and glides":     ["drawer", "slide"],
    "light bulbs":            ["light bulb", "lamp"],
    "timers":                 ["timer"],
    "capacitors":             ["capacitor"],
    "compressors":            ["compressor"],
    "sensors":                ["sensor", "thermistor"],
    "brackets and flanges":   ["bracket", "flange"],
    "caps and lids":          ["cap", "lid", "cover"],
    "wire plugs and connectors": ["wire harness", "connector", "plug"],
    "belts":                  ["belt"],
    "springs and shock absorbers": ["spring", "shock absorber"],
    "panels":                 ["panel"],
    "wheels and rollers":     ["wheel", "roller", "caster"],
    "hardware":               ["screw", "bolt", "nut", "clip"],
    "hoses and tubes":        ["hose", "tube"],
    "fuses":                  ["fuse", "thermal fuse"],
    "circuit boards and touch pads": ["control board", "touch pad", "keypad", "pcb"],
    "ducts and vents":        ["duct", "vent"],
    "elements and burners":   ["heating element", "element", "burner"],
}


def classify_part_type(part_name):
    """Return best matching part_type for a part name, or None."""
    name_lower = part_name.lower()
    for ptype, keywords in _PART_TYPE_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return ptype
    return None


def main():
    DATA.mkdir(exist_ok=True)

    # ── Load all sources ──────────────────────────────────────────────────────
    parts_raw     = load("parts_raw.json") or []
    sitemap_parts = load("sitemap_parts.json") or []
    repairs       = load("repairs.json") or []
    blogs         = load("blogs.json")  # may not exist yet
    ptls          = load("ptls.json") or []
    bam           = load("brand_appliance_map.json") or {}
    existing_mpm  = load("model_part_map.json") or {}

    print(f"Loaded: {len(parts_raw)} scraped parts, {len(sitemap_parts)} sitemap parts")
    print(f"        {len(repairs)} repair guides, {len(ptls)} PTL entries")
    print(f"        {len(blogs) if blogs else 0} blog articles")
    print(f"        {len(existing_mpm)} model->parts entries (existing model_part_map)")

    # ── 1. REBUILD symptom_part_map from actual part symptom strings ───────────
    print("\nBuilding symptom_part_map...")
    symptom_part_map = defaultdict(set)

    # Normalize repair guide symptoms -> create canonical keys
    repair_symptom_keys = set()
    for r in repairs:
        if r.get("symptom") and r.get("appliance"):
            key = f"{r['appliance']}|{r['symptom']}"
            repair_symptom_keys.add(key)
            # Also add without brand name (if symptom is just a brand name, skip)

    # Build from parts_raw.json symptoms
    parts_by_ps = {}
    for part in parts_raw:
        ps = part.get("part_number", "")
        if not ps:
            continue
        parts_by_ps[ps] = part
        category = part.get("category", "")
        symptoms = part.get("symptoms", [])
        for sym in symptoms:
            norm = normalize_symptom(sym)
            if not norm or len(norm) < 4:
                continue
            # Try to match against repair guide symptom keys
            matched = False
            for rkey in repair_symptom_keys:
                appliance, rsymptom = rkey.split("|", 1)
                if appliance != category:
                    continue
                rnorm = normalize_symptom(rsymptom)
                if rnorm in norm or norm in rnorm:
                    symptom_part_map[rkey].add(ps)
                    matched = True
            # Also add under generic key
            generic_key = f"{category}|{norm}"
            symptom_part_map[generic_key].add(ps)

    # Convert to sorted lists, filter very small sets
    symptom_part_map_out = {}
    for key, ps_set in sorted(symptom_part_map.items()):
        if len(ps_set) > 0:
            symptom_part_map_out[key] = sorted(ps_set)

    print(f"  symptom_part_map: {len(symptom_part_map_out)} keys, "
          f"{sum(len(v) for v in symptom_part_map_out.values())} total part refs")

    (DATA / "symptom_part_map.json").write_text(
        json.dumps(symptom_part_map_out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  Saved -> data/symptom_part_map.json")

    # ── 2. REBUILD part_type_map from part names + PTL data ───────────────────
    print("\nBuilding part_type_map...")
    part_type_map = defaultdict(lambda: {"brands": [], "parts": [], "part_names": []})

    # From scraped parts: classify each part by name keywords
    for part in parts_raw:
        ps = part.get("part_number", "")
        name = part.get("name", "")
        brand = part.get("brand", "")
        category = part.get("category", "")
        if not ps or not name or not category:
            continue
        ptype = classify_part_type(name)
        if ptype:
            key = f"{category}|{ptype}"
            if ps not in part_type_map[key]["parts"]:
                part_type_map[key]["parts"].append(ps)
            if brand and brand not in part_type_map[key]["brands"]:
                part_type_map[key]["brands"].append(brand)
            if name not in part_type_map[key]["part_names"]:
                part_type_map[key]["part_names"].append(name)

    # Merge in PTL data (has parts from direct scraping)
    for ptl in ptls:
        ptype = ptl.get("part_type", "").lower()
        appliance = ptl.get("appliance", "")
        brand = ptl.get("brand", "")
        ps_nums = ptl.get("parts_ps_nums", [])
        if not ptype or not appliance or not ps_nums:
            continue
        key = f"{appliance}|{ptype}"
        for ps in ps_nums:
            if ps not in part_type_map[key]["parts"]:
                part_type_map[key]["parts"].append(ps)
        if brand and brand not in part_type_map[key]["brands"]:
            part_type_map[key]["brands"].append(brand)

    # Remove part_names from output (internal only), convert to dict
    part_type_map_out = {}
    for key, val in sorted(part_type_map.items()):
        part_type_map_out[key] = {
            "brands": val["brands"],
            "parts": val["parts"],
            "count": len(val["parts"]),
        }

    print(f"  part_type_map: {len(part_type_map_out)} keys, "
          f"{sum(v['count'] for v in part_type_map_out.values())} total part refs")

    (DATA / "part_type_map.json").write_text(
        json.dumps(part_type_map_out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  Saved -> data/part_type_map.json")

    # ── 3. REBUILD model_part_map from parts_raw.json + existing data ─────────
    # Output format: {model_number: {"parts": [ps_nums], "category": str}}
    print("\nBuilding model_part_map...")
    model_parts = defaultdict(set)
    model_category = {}  # model -> category

    # Seed from existing — handle list format {model: [ps_nums]}
    # and dict format {model: {"parts": [...], "category": str}}
    for model, entry in existing_mpm.items():
        if isinstance(entry, list):
            # Validate: only add strings that look like PS numbers
            for ps in entry:
                if isinstance(ps, str) and re.match(r"PS\d+", ps):
                    model_parts[model].add(ps)
        elif isinstance(entry, dict):
            parts_val = entry.get("parts", [])
            if isinstance(parts_val, list):
                for ps in parts_val:
                    if isinstance(ps, str) and re.match(r"PS\d+", ps):
                        model_parts[model].add(ps)
            if entry.get("category") in ("refrigerator", "dishwasher"):
                model_category[model] = entry["category"]

    # Add from parts_raw.json compatible_models
    added = 0
    for part in parts_raw:
        ps = part.get("part_number", "")
        cat = part.get("category", "")
        models = part.get("compatible_models", [])
        for model in models:
            if isinstance(model, str) and model and ps:
                if ps not in model_parts[model]:
                    model_parts[model].add(ps)
                    added += 1
                if cat and model not in model_category:
                    model_category[model] = cat

    # Build sitemap category index for fallback
    sitemap_cat = {}
    for p in sitemap_parts:
        ps_num = p.get("ps_num", "")
        cat = p.get("category", "")
        if ps_num and cat:
            sitemap_cat[f"PS{ps_num}"] = cat

    model_part_map_out = {}
    for model, ps_set in model_parts.items():
        ps_list = sorted(ps_set)
        cat = model_category.get(model, "")
        if not cat:
            for ps in ps_list[:5]:
                cat = sitemap_cat.get(ps, "")
                if cat:
                    break
        model_part_map_out[model] = {"parts": ps_list, "category": cat}

    print(f"  model_part_map: {len(model_part_map_out)} models, +{added} new part refs")

    (DATA / "model_part_map.json").write_text(
        json.dumps(model_part_map_out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  Saved -> data/model_part_map.json")

    # ── 4. BLOG → part map (if blogs.json exists) ──────────────────────────────
    if blogs:
        print("\nBuilding blog_part_map...")
        blog_part_map = {}
        topic_part_map = defaultdict(set)

        for blog in blogs:
            url = blog.get("url", "")
            ps_nums = blog.get("parts_mentioned", [])
            appliance = blog.get("appliance", "")
            topic_kws = blog.get("symptom_keywords", [])

            if ps_nums:
                blog_part_map[url] = ps_nums

            for kw in (topic_kws or []):
                kw_norm = normalize_symptom(kw)
                if kw_norm:
                    for ps in ps_nums:
                        topic_part_map[f"{appliance}|{kw_norm}"].add(ps)

        topic_part_map_out = {k: sorted(v) for k, v in topic_part_map.items() if v}

        (DATA / "blog_part_map.json").write_text(
            json.dumps(blog_part_map, indent=2, ensure_ascii=False), encoding="utf-8")
        (DATA / "topic_part_map.json").write_text(
            json.dumps(topic_part_map_out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  blog_part_map: {len(blog_part_map)} blog URLs with parts")
        print(f"  topic_part_map: {len(topic_part_map_out)} topic keys")
        print("  Saved -> data/blog_part_map.json, data/topic_part_map.json")

    # ── 5. RELATIONAL SUMMARY ─────────────────────────────────────────────────
    print("\nBuilding relational_summary.json...")

    # Aggregate parts coverage stats
    all_ps_in_symptoms = set()
    for v in symptom_part_map_out.values():
        all_ps_in_symptoms.update(v)

    all_ps_in_types = set()
    for v in part_type_map_out.values():
        all_ps_in_types.update(v["parts"])

    all_ps_in_models = set()
    for v in model_part_map_out.values():
        all_ps_in_models.update(v)

    # Brand stats from sitemap_parts
    from collections import Counter
    brand_counts = Counter(p.get("brand", "?").upper() for p in sitemap_parts)
    top_brands = [{"brand": b, "count": n} for b, n in brand_counts.most_common(20)]

    # Category stats
    cat_counts = Counter(p.get("category", "?") for p in sitemap_parts)

    summary = {
        "scraped_parts": len(parts_raw),
        "sitemap_parts": len(sitemap_parts),
        "sitemap_refrigerator": cat_counts.get("refrigerator", 0),
        "sitemap_dishwasher": cat_counts.get("dishwasher", 0),
        "sitemap_models": len(load("sitemap_models.json") or []),
        "repair_guides": len(repairs),
        "blogs": len(blogs) if blogs else 0,
        "category_pages": len(load("category_pages.json") or []),
        "ptl_entries": len(ptls),
        "symptom_keys": len(symptom_part_map_out),
        "parts_with_symptoms": len(all_ps_in_symptoms),
        "part_type_keys": len(part_type_map_out),
        "parts_with_types": len(all_ps_in_types),
        "model_keys": len(model_part_map_out),
        "parts_with_models": len(all_ps_in_models),
        "brand_appliance_keys": len(bam),
        "top_brands": top_brands,
    }

    (DATA / "relational_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Saved -> data/relational_summary.json")

    # ── Print overview ────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("RELATIONAL INDEX SUMMARY")
    print("="*60)
    print(f"Parts scraped (full details):  {len(parts_raw):>6}")
    print(f"Parts in sitemap (classified): {len(sitemap_parts):>6}")
    print(f"  Refrigerator:                {cat_counts.get('refrigerator',0):>6}")
    print(f"  Dishwasher:                  {cat_counts.get('dishwasher',0):>6}")
    print(f"Symptoms mapped:               {len(symptom_part_map_out):>6}")
    print(f"  Parts with symptoms:         {len(all_ps_in_symptoms):>6}")
    print(f"Part types mapped:             {len(part_type_map_out):>6}")
    print(f"  Parts with type:             {len(all_ps_in_types):>6}")
    print(f"Models in model_part_map:      {len(model_part_map_out):>6}")
    print(f"  Parts with model refs:       {len(all_ps_in_models):>6}")
    print(f"Brand x Appliance keys:        {len(bam):>6}")
    if blogs:
        blog_with_parts = sum(1 for v in blog_part_map.values() if v)
        print(f"Blog articles with parts:      {blog_with_parts:>6}")
    print()

    # Top part types
    top_types = sorted(part_type_map_out.items(), key=lambda x: -x[1]["count"])[:10]
    print("Top 10 part types by part count:")
    for key, val in top_types:
        print(f"  {key:50s}  {val['count']:3d} parts  {len(val['brands'])} brands")

    print("\nDone. Run embed_and_index.py to rebuild FAISS index.")


if __name__ == "__main__":
    main()
