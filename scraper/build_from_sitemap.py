"""
PartSelect sitemap-based parts and models database builder.

Classification strategy (no network required — pure local XML):
  Tier 1: URL slug keywords (conservative, high-precision)
  Tier 2: Brand + MPN prefix rules (derived from ground-truth scraped data)
  Exclusions: known non-fridge/dish MPN prefixes (e.g. GE WB = oven)

All 101,843 PartDetail URLs are scanned; only confirmed fridge/dish parts kept.

Outputs:
  data/sitemap_parts.json  -- [{ps_num, url, brand, mpn, category}, ...]
  data/sitemap_models.json -- [model_number, ...]

Run from scraper/ directory:  python build_from_sitemap.py
"""

import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

XML_DIR  = Path("../xml")
DATA_DIR = Path("data")

PART_FILES = [
    "PartSelect.com_Sitemap_PartDetail_1_50000.xml",
    "PartSelect.com_Sitemap_PartDetail_50001_100000.xml",
    "PartSelect.com_Sitemap_PartDetail_100001_150000.xml",
]
MODEL_FILES = [
    "PartSelect.com_Sitemap_Models_1_50000.xml",
    "PartSelect.com_Sitemap_Models_50001_100000.xml",
    "PartSelect.com_Sitemap_Models_100001_150000.xml",
    "PartSelect.com_Sitemap_Models_150001_200000.xml",
    "PartSelect.com_Sitemap_Models_200001_250000.xml",
    "PartSelect.com_Sitemap_Models_250001_300000.xml",
    "PartSelect.com_Sitemap_Models_300001_350000.xml",
    "PartSelect.com_Sitemap_Models_350001_400000.xml",
]

# ── URL parser ────────────────────────────────────────────────────────────────

_PART_URL_RE = re.compile(
    r"/PS(?P<ps>\d+)-(?P<brand>[^-]+)-(?P<mpn>[^-]+)-(?P<slug>.+)\.htm$",
    re.I,
)

# ── Tier 1: Slug keyword rules ────────────────────────────────────────────────
# Dishwasher checked first — some terms (e.g. "rack") appear in both.
# Only include terms that are genuinely appliance-specific in the slug context.

_DISH_SLUG_RE = re.compile(
    r"dishwasher"
    r"|spray[\-_]arm"
    r"|wash[\-_]arm"
    r"|silverware[\-_]basket"
    r"|utensil[\-_]basket"
    r"|dish[\-_]rack"
    r"|dishrack"
    r"|rinse[\-_]aid"
    r"|detergent[\-_]dispenser"
    r"|rack[\-_]adjuster"
    r"|rack[\-_]tine"
    r"|tine[\-_]row"
    r"|sump[\-_]assembly"
    r"|dish[\-_]tub"
    r"|lower[\-_]dishrack"
    r"|upper[\-_]dishrack",
    re.I,
)

_FRIDGE_SLUG_RE = re.compile(
    r"refrigerator"
    r"|refrigerat"
    r"|ice[\-_]maker"
    r"|ice[\-_]dispens"
    r"|ice[\-_]bucket"
    r"|ice[\-_]tray"
    r"|ice[\-_]auger"
    r"|ice[\-_]container"
    r"|crisper[\-_]drawer"
    r"|crisper[\-_]pan"
    r"|deli[\-_]drawer"
    r"|deli[\-_]pan"
    r"|door[\-_]bin"
    r"|cheese[\-_]drawer"
    r"|fresh[\-_]food"
    r"|pantry[\-_]drawer"
    r"|mullion"
    r"|evaporator[\-_]fan"
    r"|evaporator[\-_]coil"
    r"|defrost[\-_]heater"
    r"|defrost[\-_]thermostat"
    r"|defrost[\-_]timer"
    r"|defrost[\-_]control"
    r"|freezer[\-_]drawer"
    r"|freezer[\-_]door"
    r"|freezer[\-_]shelf"
    r"|freezer[\-_]basket"
    r"|shelf[\-_]glass"
    r"|glass[\-_]shelf"
    r"|refrigerator[\-_]shelf"
    r"|door[\-_]shelf"
    r"|door[\-_]rack",
    re.I,
)

# ── Tier 2: Brand + MPN prefix rules ─────────────────────────────────────────
# Each entry: (brand_upper, compiled_mpn_re, category)
# Derived from ground-truth analysis of 1,629 correctly scraped parts.
# Ordered: more specific rules first.

_BRAND_MPN_RULES: list[tuple[str, re.Pattern, str]] = []


def _add_rule(brand: str, mpn_pattern: str, category: str) -> None:
    _BRAND_MPN_RULES.append((brand.upper(), re.compile(mpn_pattern, re.I), category))


# GE: WR = Refrigerator, WD = Dishwasher
# WB = Range/Oven — explicitly excluded below
_add_rule("GE",      r"^WR",  "refrigerator")
_add_rule("GE",      r"^WJ",  "refrigerator")   # GE air tower / ice dispenser assembly
_add_rule("GE",      r"^WH1", "refrigerator")   # specific GE fridge sub-series
_add_rule("GE",      r"^WD",  "dishwasher")

# Samsung: DA = Refrigerator, DD/DW = Dishwasher
_add_rule("SAMSUNG", r"^DA",  "refrigerator")
_add_rule("SAMSUNG", r"^DD",  "dishwasher")

# Frigidaire: numeric prefixes for refrigerators (240x, 241x, 242x, 297x, 5303x)
# and dishwasher (1547x, 1548x, 807x)
_add_rule("FRIGIDAIRE", r"^(240|241|242|297|530[36]|218[79]|215|216|29[0-9])", "refrigerator")
_add_rule("FRIGIDAIRE", r"^(1547|1548|1543|807)",                               "dishwasher")

# Whirlpool: WP-prefixed parts that are fridge-specific (from ground truth analysis)
# WP2x and WP6x prefixes are predominantly refrigerator; WP85/WP82 are dishwasher
_add_rule("WHIRLPOOL", r"^WP(2|6|12|21|22|23|43|48|67|61)",  "refrigerator")
_add_rule("WHIRLPOOL", r"^(EDR|R01|WPM)",                     "refrigerator")
_add_rule("WHIRLPOOL", r"^WP(82|85)",                         "dishwasher")
_add_rule("WHIRLPOOL", r"^W107",                              "dishwasher")

# Bosch: 001xxxx = dishwasher, 004xxxx = refrigerator
_add_rule("BOSCH",   r"^001",  "dishwasher")
_add_rule("BOSCH",   r"^004",  "refrigerator")

# LG: ADC, AEQ, AAP, AJU, AJP, MAN, EBR = refrigerator; AGM = dishwasher
_add_rule("LG",      r"^(AA|AD|AED|AEQ|AJP|AJU|EB|MA|MH)", "refrigerator")
_add_rule("LG",      r"^(4681|5989|5220|598)",               "refrigerator")
_add_rule("LG",      r"^AGM",                                "dishwasher")

# ── Exclusions (known non-fridge/dish MPN families) ───────────────────────────
# If a URL matches an exclusion, skip it even if it matched a rule above.

_BRAND_MPN_EXCLUSIONS: list[tuple[str, re.Pattern]] = []


def _add_excl(brand: str, mpn_pattern: str) -> None:
    _BRAND_MPN_EXCLUSIONS.append((brand.upper(), re.compile(mpn_pattern, re.I)))


_add_excl("GE", r"^WB")   # GE WB = Range/Oven parts
_add_excl("GE", r"^WH[^1]")  # GE WH (non-WH1) = Washer parts


# ── Classifier ────────────────────────────────────────────────────────────────

def classify(url: str) -> tuple[str | None, str, str, str]:
    """
    Returns (category, ps_num, brand, mpn).
    category is 'refrigerator', 'dishwasher', or None (skip).
    """
    m = _PART_URL_RE.search(url)
    if not m:
        return None, "", "", ""

    ps    = m.group("ps")
    brand = m.group("brand")
    mpn   = m.group("mpn")
    slug  = m.group("slug")

    brand_up = brand.upper()
    mpn_up   = mpn.upper()

    # Check exclusions first
    for excl_brand, excl_re in _BRAND_MPN_EXCLUSIONS:
        if brand_up == excl_brand and excl_re.match(mpn_up):
            return None, ps, brand, mpn

    # Tier 2: brand + MPN prefix (before slug so brand logic takes priority)
    for rule_brand, rule_re, category in _BRAND_MPN_RULES:
        if brand_up == rule_brand and rule_re.match(mpn_up):
            return category, ps, brand, mpn

    # Tier 1: URL slug keywords
    if _DISH_SLUG_RE.search(slug):
        return "dishwasher", ps, brand, mpn
    if _FRIDGE_SLUG_RE.search(slug):
        return "refrigerator", ps, brand, mpn

    return None, ps, brand, mpn


# ── XML helpers ───────────────────────────────────────────────────────────────

def parse_locs(path: Path) -> list[str]:
    locs = []
    try:
        for _event, elem in ET.iterparse(str(path), events=("end",)):
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "loc" and elem.text:
                locs.append(elem.text.strip())
            elem.clear()
    except Exception as exc:
        print(f"  WARN: {path.name}: {exc}", flush=True)
    return locs


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    # ── Part sitemaps ─────────────────────────────────────────────────────────
    print("=== Classifying PartDetail sitemaps ===", flush=True)
    entries: list[dict] = []
    seen_ps: set[str]   = set()
    tier1_count = tier2_count = 0

    for filename in PART_FILES:
        path = XML_DIR / filename
        if not path.exists():
            print(f"  SKIP {filename} (not found)", flush=True)
            continue
        locs = parse_locs(path)
        before = len(entries)
        for url in locs:
            category, ps, brand, mpn = classify(url)
            if not category or ps in seen_ps or not ps:
                continue
            seen_ps.add(ps)
            entries.append({
                "ps_num":   ps,
                "url":      url,
                "brand":    brand,
                "mpn":      mpn,
                "category": category,
            })
        added = len(entries) - before
        print(f"  {filename}: {len(locs):>6} URLs -> +{added:>4} fridge/dish (total {len(entries)})",
              flush=True)

    fridge_n = sum(1 for e in entries if e["category"] == "refrigerator")
    dish_n   = sum(1 for e in entries if e["category"] == "dishwasher")
    print(f"\nTotal: {fridge_n} refrigerator + {dish_n} dishwasher = {len(entries)} parts\n",
          flush=True)

    # Per-brand breakdown
    from collections import Counter
    brand_cat = Counter((e["brand"].upper(), e["category"]) for e in entries)
    print("Top brands in results:")
    from collections import defaultdict
    brand_totals = defaultdict(int)
    for (b, c), n in brand_cat.items():
        brand_totals[b] += n
    for b, total in sorted(brand_totals.items(), key=lambda x: -x[1])[:15]:
        f = brand_cat.get((b, "refrigerator"), 0)
        d = brand_cat.get((b, "dishwasher"), 0)
        print(f"  {b:20s} {total:4d}  (fridge {f:4d}  dish {d:4d})")

    print(flush=True)
    parts_out = DATA_DIR / "sitemap_parts.json"
    parts_out.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved -> {parts_out}", flush=True)

    # ── Model sitemaps ────────────────────────────────────────────────────────
    print("\n=== Model sitemaps ===", flush=True)
    all_models: list[str] = []
    seen_models: set[str] = set()
    for filename in MODEL_FILES:
        path = XML_DIR / filename
        if not path.exists():
            print(f"  SKIP {filename} (not found)", flush=True)
            continue
        locs = parse_locs(path)
        added = 0
        for url in locs:
            mm = re.search(r"/Models/([^/?#]+)/?$", url)
            if mm:
                mn = mm.group(1).strip()
                if mn and mn not in seen_models:
                    seen_models.add(mn)
                    all_models.append(mn)
                    added += 1
        print(f"  {filename}: {added} models", flush=True)
    models_out = DATA_DIR / "sitemap_models.json"
    models_out.write_text(json.dumps(all_models, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTotal: {len(all_models)} models -> {models_out}", flush=True)

    print("\nDone. Next: python scrape_parts.py")


if __name__ == "__main__":
    main()
