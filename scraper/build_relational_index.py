"""
build_relational_index.py
Consolidates scraped part data into relational maps used by the backend.

Inputs (all in data/):
  parts_raw.json           - scraped parts with names, symptoms, models
  sitemap_parts.json       - classified parts from sitemaps
  model_part_map.json      - existing model -> PS nums (enriched in place)

Outputs (all in data/):
  symptom_part_map.json    - rebuilt from part symptom strings
  part_type_map.json       - rebuilt from part names + keyword mapping
  model_part_map.json      - enriched with compatible_models from parts_raw
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
    s = s.lower().strip().rstrip(".").strip()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


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
    name_lower = part_name.lower()
    for ptype, keywords in _PART_TYPE_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return ptype
    return None


def main():
    DATA.mkdir(exist_ok=True)

    parts_raw     = load("parts_raw.json") or []
    sitemap_parts = load("sitemap_parts.json") or []
    existing_mpm  = load("model_part_map.json") or {}

    print(f"Loaded: {len(parts_raw)} scraped parts, {len(sitemap_parts)} sitemap parts")

    # ── 1. symptom_part_map ───────────────────────────────────────────────────
    print("\nBuilding symptom_part_map...")
    symptom_part_map: dict[str, set] = defaultdict(set)

    parts_by_ps = {}
    for part in parts_raw:
        ps = part.get("part_number", "")
        if not ps:
            continue
        parts_by_ps[ps] = part
        category = part.get("category", "")
        for sym in part.get("symptoms", []):
            norm = normalize_symptom(sym)
            if norm and len(norm) >= 4:
                symptom_part_map[f"{category}|{norm}"].add(ps)

    symptom_part_map_out = {
        key: sorted(ps_set)
        for key, ps_set in sorted(symptom_part_map.items())
        if ps_set
    }
    print(f"  {len(symptom_part_map_out)} keys, "
          f"{sum(len(v) for v in symptom_part_map_out.values())} part refs")
    (DATA / "symptom_part_map.json").write_text(
        json.dumps(symptom_part_map_out, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── 2. part_type_map ──────────────────────────────────────────────────────
    print("\nBuilding part_type_map...")
    part_type_map: dict[str, dict] = defaultdict(lambda: {"brands": [], "parts": [], "part_names": []})

    for part in parts_raw:
        ps       = part.get("part_number", "")
        name     = part.get("name", "")
        brand    = part.get("brand", "")
        category = part.get("category", "")
        if not ps or not name or not category:
            continue
        ptype = classify_part_type(name)
        if ptype:
            key = f"{category}|{ptype}"
            entry = part_type_map[key]
            if ps not in entry["parts"]:
                entry["parts"].append(ps)
            if brand and brand not in entry["brands"]:
                entry["brands"].append(brand)

    part_type_map_out = {
        key: {"brands": val["brands"], "parts": val["parts"], "count": len(val["parts"])}
        for key, val in sorted(part_type_map.items())
    }
    print(f"  {len(part_type_map_out)} keys, "
          f"{sum(v['count'] for v in part_type_map_out.values())} part refs")
    (DATA / "part_type_map.json").write_text(
        json.dumps(part_type_map_out, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── 3. model_part_map ─────────────────────────────────────────────────────
    print("\nBuilding model_part_map...")
    model_parts: dict[str, set] = defaultdict(set)
    model_category: dict[str, str] = {}

    for model, entry in existing_mpm.items():
        if isinstance(entry, list):
            for ps in entry:
                if isinstance(ps, str) and re.match(r"PS\d+", ps):
                    model_parts[model].add(ps)
        elif isinstance(entry, dict):
            for ps in entry.get("parts", []):
                if isinstance(ps, str) and re.match(r"PS\d+", ps):
                    model_parts[model].add(ps)
            if entry.get("category") in ("refrigerator", "dishwasher"):
                model_category[model] = entry["category"]

    added = 0
    for part in parts_raw:
        ps  = part.get("part_number", "")
        cat = part.get("category", "")
        for model in part.get("compatible_models", []):
            if isinstance(model, str) and model and ps:
                if ps not in model_parts[model]:
                    model_parts[model].add(ps)
                    added += 1
                if cat and model not in model_category:
                    model_category[model] = cat

    sitemap_cat = {
        f"PS{p['ps_num']}": p["category"]
        for p in sitemap_parts
        if p.get("ps_num") and p.get("category")
    }

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

    print(f"  {len(model_part_map_out)} models, +{added} new part refs")
    (DATA / "model_part_map.json").write_text(
        json.dumps(model_part_map_out, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print(f"Parts scraped:        {len(parts_raw):>6}")
    print(f"Symptom keys:         {len(symptom_part_map_out):>6}")
    print(f"Part type keys:       {len(part_type_map_out):>6}")
    print(f"Model keys:           {len(model_part_map_out):>6}")
    print("\nTop 10 part types:")
    for key, val in sorted(part_type_map_out.items(), key=lambda x: -x[1]["count"])[:10]:
        print(f"  {key:50s}  {val['count']:3d} parts")
    print("\nDone. Run embed_and_index.py to rebuild FAISS index.")


if __name__ == "__main__":
    main()
