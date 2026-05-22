import re
import json
import httpx
import numpy as np
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Optional

# ── In-memory cart ────────────────────────────────────────────────────────────
_carts: dict[str, list[dict]] = {}

# ── FAISS / sentence-transformers (lazy-loaded on first search) ───────────────
_faiss_index    = None
_faiss_metadata: list[dict] = []
_st_model       = None
_DATA_DIR = Path(__file__).parent / "data"

# ── Relational maps (loaded once at startup) ──────────────────────────────────
# model_part_map: {model_number: {"category": str, "parts": [ps_num, ...]}}
# symptom_part_map: {"category|symptom": [ps_num, ...]}
# part_type_map: {"category|type": {"parts": [...], "brands": [...]}}
# brand_appliance_map: {"Brand|appliance": {"parts": [...], ...}}
_model_part_map: dict[str, dict] = {}
_symptom_part_map: dict[str, list] = {}
_part_type_map: dict[str, dict] = {}
_brand_appliance_map: dict[str, dict] = {}
_model_map_loaded = False
_relational_maps_loaded = False


def _load_model_map() -> None:
    global _model_part_map, _model_map_loaded
    if _model_map_loaded:
        return
    _model_map_loaded = True
    map_path = _DATA_DIR / "model_part_map.json"
    if not map_path.exists():
        return
    try:
        _model_part_map = json.loads(map_path.read_text(encoding="utf-8"))
        print(f"[model_map] Loaded {len(_model_part_map)} models")
    except Exception as e:
        print(f"[model_map] Load failed: {e}")


def _load_relational_maps() -> None:
    global _symptom_part_map, _part_type_map, _brand_appliance_map, _relational_maps_loaded
    if _relational_maps_loaded:
        return
    _relational_maps_loaded = True
    for attr, fname in [
        ("symptom",    "symptom_part_map.json"),
        ("part_type",  "part_type_map.json"),
        ("brand",      "brand_appliance_map.json"),
    ]:
        path = _DATA_DIR / fname
        if not path.exists():
            print(f"[relational] {fname} not found, skipping")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if attr == "symptom":
                _symptom_part_map = data
            elif attr == "part_type":
                _part_type_map = data
            else:
                _brand_appliance_map = data
            print(f"[relational] Loaded {fname}: {len(data)} keys")
        except Exception as e:
            print(f"[relational] Failed to load {fname}: {e}")


def _load_faiss() -> bool:
    """Load FAISS index + metadata + ST model on first call. Cached after that."""
    global _faiss_index, _faiss_metadata, _st_model
    if _faiss_index is not None:
        return True
    index_path = _DATA_DIR / "faiss_index.bin"
    meta_path  = _DATA_DIR / "parts_metadata.json"
    if not index_path.exists() or not meta_path.exists():
        return False
    try:
        import faiss
        from sentence_transformers import SentenceTransformer
        _faiss_index    = faiss.read_index(str(index_path))
        _faiss_metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        _st_model       = SentenceTransformer("all-MiniLM-L6-v2")
        print(f"[FAISS] Loaded {_faiss_index.ntotal} vectors")
        _load_model_map()
        _load_relational_maps()
        return True
    except Exception as e:
        print(f"[FAISS] Load failed: {e}")
        return False


def _clean_video_url(url: str) -> str:
    """Return url only if it links to a specific video, not a generic channel page."""
    if url and "watch?v=" in url:
        return url
    return ""


def _enrich_parts(ps_list: list[str], limit: int = 8) -> list[dict]:
    """Enrich a list of PS numbers with full metadata from the FAISS metadata store."""
    if not ps_list:
        return []
    ps_set = set(ps_list[:100])
    if _faiss_metadata:
        enriched = [
            {
                "part_number":    p["part_number"],
                "name":           p["name"],
                "price":          p["price"],
                "brand":          p["brand"],
                "category":       p["category"],
                "image_url":      p["image_url"],
                "description":    p["description"],
                "rating":         p.get("rating", 0),
                "review_count":   p.get("review_count", 0),
                "symptoms":       p.get("symptoms", []),
                "install_difficulty": p.get("install_difficulty", ""),
                "install_time":   p.get("install_time", ""),
                "video_url":      _clean_video_url(p.get("video_url", "")),
                "url":            p.get("url", ""),
            }
            for p in _faiss_metadata
            if p.get("part_number") in ps_set
               and float(p.get("price") or 0) > 0   # exclude zero-price parts
        ]
        if enriched:
            return enriched[:limit]
    return [{"part_number": pn} for pn in list(ps_set)[:limit]]


# ── Tool definitions ──────────────────────────────────────────────────────────
TOOL_DEFINITIONS = [
    {
        "name": "search_catalog",
        "description": (
            "Search the PartSelect product catalog semantically. Use for any query about "
            "finding parts, symptoms, broken appliances, or product categories. "
            "Works for refrigerator and dishwasher parts only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query, e.g. 'ice maker not working', 'dishwasher door latch', 'water inlet valve'",
                },
                "category": {
                    "type": "string",
                    "enum": ["refrigerator", "dishwasher"],
                    "description": "Filter by appliance category",
                },
                "brand": {
                    "type": "string",
                    "description": "Filter by brand, e.g. 'Whirlpool', 'Samsung', 'GE'",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_part_details",
        "description": (
            "Get detailed information about a specific part by its part number (PS#####). "
            "Returns specs, compatibility list, installation instructions, and current price. "
            "Always call this when a user mentions a specific part number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "part_number": {
                    "type": "string",
                    "description": "The PartSelect part number, e.g. 'PS11752778'",
                }
            },
            "required": ["part_number"],
        },
    },
    {
        "name": "check_model_compatibility",
        "description": (
            "Find all parts compatible with a specific appliance model number. "
            "Call this whenever a user mentions their appliance model number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model_number": {
                    "type": "string",
                    "description": "The appliance model number, e.g. 'WDT780SAEM1'",
                }
            },
            "required": ["model_number"],
        },
    },
    {
        "name": "manage_cart",
        "description": "Add items to cart, remove items, or view the current cart contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "remove", "view"],
                    "description": "Cart action to perform",
                },
                "part_number": {
                    "type": "string",
                    "description": "Part number for add/remove actions",
                },
                "name": {
                    "type": "string",
                    "description": "Part name (used when adding)",
                },
                "price": {
                    "type": "number",
                    "description": "Part price in USD (used when adding)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "get_order",
        "description": "Look up order status and tracking information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Specific order ID to look up (optional — omit to see recent orders)",
                }
            },
            "required": [],
        },
    },
    {
        "name": "find_parts_by_symptom",
        "description": (
            "Find parts that fix a specific appliance symptom or problem. "
            "Use this when users describe what is wrong with their appliance, e.g. "
            "'not making ice', 'leaking water', 'door won't close', 'not draining', "
            "'noisy', 'not cooling'. More precise than search_catalog for symptom-driven queries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symptom": {
                    "type": "string",
                    "description": "The symptom or problem, e.g. 'not making ice', 'leaking water', 'door won\\'t seal', 'not draining'",
                },
                "category": {
                    "type": "string",
                    "enum": ["refrigerator", "dishwasher"],
                    "description": "Filter by appliance type",
                },
            },
            "required": ["symptom"],
        },
    },
    {
        "name": "find_parts_by_type",
        "description": (
            "Find parts by their component type or category. "
            "Use when users ask for a specific kind of part, e.g. 'ice makers', "
            "'door gaskets', 'spray arms', 'water filters', 'drain pumps', 'handles', 'shelves', 'racks'. "
            "Supports optional brand and appliance category filters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "part_type": {
                    "type": "string",
                    "description": "The type of part, e.g. 'ice makers', 'door gaskets', 'spray arms', 'water filters', 'drain pumps', 'handles', 'shelves', 'dish racks'",
                },
                "category": {
                    "type": "string",
                    "enum": ["refrigerator", "dishwasher"],
                    "description": "Filter by appliance type",
                },
                "brand": {
                    "type": "string",
                    "description": "Filter by brand, e.g. 'Whirlpool', 'Samsung', 'GE', 'Bosch', 'LG'",
                },
            },
            "required": ["part_type"],
        },
    },
    {
        "name": "find_parts_by_brand",
        "description": (
            "Find all available parts for a specific appliance brand. "
            "Use when a user mentions their appliance brand without a model number, "
            "e.g. 'I have a Samsung fridge', 'looking for Bosch dishwasher parts', "
            "'what GE refrigerator parts do you carry'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "brand": {
                    "type": "string",
                    "description": "The appliance brand, e.g. 'Whirlpool', 'Samsung', 'GE', 'LG', 'Bosch', 'Frigidaire', 'Maytag'",
                },
                "category": {
                    "type": "string",
                    "enum": ["refrigerator", "dishwasher"],
                    "description": "Filter by appliance type",
                },
            },
            "required": ["brand"],
        },
    },
]


# ── Tool implementations ───────────────────────────────────────────────────────

async def search_catalog(
    query: str,
    category: Optional[str] = None,
    brand: Optional[str] = None,
) -> list:
    """Semantic search via local FAISS index (sentence-transformers, no API keys)."""
    if not _load_faiss():
        return [{"error": "Catalog index not available. Run embed_and_index.py to build it."}]

    try:
        q_vec = _st_model.encode([query], normalize_embeddings=True).astype(np.float32)
        k = min(50, _faiss_index.ntotal)
        scores, idxs = _faiss_index.search(q_vec, k)

        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0 or idx >= len(_faiss_metadata):
                continue
            item = _faiss_metadata[idx]
            # Only return actual part records to Claude (not repair guides or blogs)
            if item.get("type", "part") != "part":
                continue
            if not item.get("part_number"):
                continue
            if float(item.get("price") or 0) <= 0:
                continue
            if category and item.get("category") != category:
                continue
            if brand and item.get("brand", "").lower() != brand.lower():
                continue
            results.append(item)
            if len(results) == 5:
                break
        return results
    except Exception as e:
        return [{"error": f"Search failed: {e}"}]


def _parse_part_html(html: str, pn: str, url: str) -> dict | None:
    """Parse a PartSelect part page (live or archived) into a part dict."""
    soup = BeautifulSoup(html, "html.parser")

    if "Page cannot be crawled" in html or "Page Not Found" in html[:2000]:
        return None

    # Prefer the <link rel="canonical"> URL over whatever we fetched from
    canonical_tag = soup.find("link", rel="canonical")
    if canonical_tag and canonical_tag.get("href", "").startswith("https://www.partselect.com/PS"):
        url = canonical_tag["href"]

    result: dict = {"part_number": f"PS{pn}", "url": url}

    h1 = soup.find("h1", class_=re.compile(r"title", re.I)) or soup.find("h1")
    if not h1:
        return None
    name = h1.get_text(strip=True)
    name = re.sub(r"^(Skip to main content|Close)", "", name).strip()
    if len(name) < 5:
        return None
    result["name"] = name

    # Price
    price_el = (
        soup.find(attrs={"itemprop": "price"})
        or soup.find("span", class_=re.compile(r"price", re.I))
    )
    if price_el:
        raw = price_el.get("content") or price_el.get_text(strip=True)
        m = re.search(r"\d+\.\d{2}", raw.replace(",", ""))
        if m:
            try:
                result["price"] = float(m.group())
            except ValueError:
                pass
    result.setdefault("price", 0.0)

    # Brand
    slug_match = re.search(r"/PS\d+-([A-Za-z]+)-", url)
    result["brand"] = slug_match.group(1) if slug_match else ""

    # Description
    desc = (
        soup.find("div", class_="pd__description")
        or soup.find(attrs={"itemprop": "description"})
    )
    result["description"] = desc.get_text(strip=True)[:600] if desc else ""

    # Symptoms
    symptoms: list[str] = []
    sym_heading = soup.find(string=re.compile(r"fixes the following symptoms|this part fixes", re.I))
    if sym_heading:
        container = sym_heading.find_parent()
        if container:
            parent = container.find_parent()
            if parent:
                for li in parent.find_all("li"):
                    text = li.get_text(strip=True)
                    if text and len(text) > 3:
                        symptoms.append(text)
    result["symptoms"] = symptoms[:10]

    # Install difficulty / time
    repair_sec = soup.find(class_=re.compile(r"repair.?rating|pd__repair", re.I))
    if repair_sec:
        text = repair_sec.get_text(" ", strip=True)
        diff_m = re.search(r"difficulty[:\s]+([A-Za-z ]+?)(?:\s+time|\s*$)", text, re.I)
        time_m = re.search(r"time[:\s]+([\w\s\-]+?)(?:\s+difficulty|\s*$)", text, re.I)
        result["install_difficulty"] = diff_m.group(1).strip()[:50] if diff_m else ""
        result["install_time"]       = time_m.group(1).strip()[:50] if time_m else ""

    # Video
    yt_iframe = soup.find("iframe", src=re.compile(r"youtube\.com|youtu\.be", re.I))
    if yt_iframe:
        result["video_url"] = yt_iframe.get("src", "")
    elif yt_el := soup.find(attrs={"data-yt-init": True}):
        vid_id = yt_el.get("data-yt-init", "")
        if vid_id:
            result["video_url"] = f"https://www.youtube.com/watch?v={vid_id}"

    # Compatible models
    compat = (
        soup.find("div", class_=re.compile(r"crossref|compat|models", re.I))
        or soup.find("section", attrs={"id": re.compile(r"compat|model", re.I)})
    )
    if compat:
        result["compatible_models"] = [
            a.get_text(strip=True)
            for a in compat.find_all("a", limit=30)
            if re.match(r"[A-Z0-9]{5,15}$", a.get_text(strip=True))
        ]

    # Image
    for img in soup.find_all("img"):
        src = img.get("src", "") or img.get("data-src", "")
        if src and not ("web.archive.org" in src and "im_" in src):
            classes = " ".join(img.get("class", []))
            if re.search(r"main|product|primary|hero|ps-main", classes, re.I):
                result["image_url"] = src
                break
    result.setdefault("image_url", "")

    # Rating
    if rating_el := soup.find(attrs={"itemprop": "ratingValue"}):
        try:
            result["rating"] = float(rating_el.get_text(strip=True))
        except ValueError:
            pass
    if review_el := soup.find(attrs={"itemprop": "reviewCount"}):
        try:
            result["review_count"] = int(review_el.get_text(strip=True).replace(",", ""))
        except ValueError:
            pass

    return result


async def _wayback_fetch(client: httpx.AsyncClient, pn: str) -> dict | None:
    """On-demand Wayback Machine lookup for any PS number."""
    try:
        cdx = await client.get(
            "https://web.archive.org/cdx/search/cdx",
            params={
                "url":      f"www.partselect.com/PS{pn}*",
                "output":   "json",
                "fl":       "original,timestamp",
                "filter":   "statuscode:200",
                "limit":    1,
                "collapse": "original",
            },
            timeout=10,
        )
        rows = cdx.json()
        if len(rows) < 2:
            return None
        orig = rows[1][0].split("?")[0]   # CDX canonical URL (full slug)
        ts   = rows[1][1]
        # Normalise to https
        canon = orig.replace("http://", "https://", 1)
        resp = await client.get(
            f"https://web.archive.org/web/{ts}/{orig}",
            timeout=30,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        # Pass CDX canonical URL so _parse_part_html uses it as the base;
        # it will still override with <link rel="canonical"> if present
        return _parse_part_html(resp.text, pn, canon)
    except Exception:
        return None


STEALTH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


async def get_part_details(part_number: str) -> dict:
    pn  = re.sub(r"[^0-9]", "", part_number)
    url = f"https://www.partselect.com/PS{pn}.htm"

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=STEALTH_HEADERS) as client:
        # 1. Try direct PartSelect fetch — use final redirect URL as the canonical URL
        try:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.text) > 2000:
                # Pass str(resp.url) as fallback; _parse_part_html overwrites with
                # <link rel="canonical"> href when present (the full slug URL)
                result = _parse_part_html(resp.text, pn, str(resp.url))
                if result:
                    result["_source"] = "live"
                    return result
        except Exception:
            pass

        # 2. Check FAISS metadata (already scraped data)
        if _load_faiss():
            match = next((p for p in _faiss_metadata if p.get("part_number") == f"PS{pn}"), None)
            if match:
                return {**match, "_source": "index"}

        # 3. On-demand Wayback Machine fetch
        wb = await _wayback_fetch(client, pn)
        if wb:
            wb["_source"] = "wayback"
            return wb

    return {"error": f"Part PS{pn} not found.", "part_number": f"PS{pn}", "url": url}


def _parts_from_map(model: str) -> list[dict]:
    """Look up compatible parts from the local relational map + FAISS metadata."""
    _load_model_map()
    entry = _model_part_map.get(model)
    if not entry:
        return []

    # Handle both dict format {"parts": [...], "category": str} and legacy list format
    if isinstance(entry, list):
        pn_set = set(entry)
    else:
        pn_set = set(entry.get("parts", []))
    if not pn_set:
        return []

    # Enrich with full metadata from FAISS if available
    if _faiss_metadata:
        enriched = [
            {
                "part_number":    p["part_number"],
                "name":           p["name"],
                "price":          p["price"],
                "brand":          p["brand"],
                "category":       p["category"],
                "image_url":      p.get("image_url", ""),
                "description":    p["description"],
                "url":            p.get("url", ""),
                "rating":         p.get("rating", 0),
                "review_count":   p.get("review_count", 0),
                "symptoms":       p.get("symptoms", []),
                "install_difficulty": p.get("install_difficulty", ""),
                "install_time":   p.get("install_time", ""),
                "video_url":      p.get("video_url", ""),
            }
            for p in _faiss_metadata
            if p.get("part_number") in pn_set
        ]
        if enriched:
            return enriched

    # Fallback: return bare part numbers when FAISS isn't loaded yet
    return [{"part_number": pn} for pn in pn_set]


async def check_model_compatibility(model_number: str) -> dict:
    model = model_number.strip().upper()
    url   = f"https://www.partselect.com/Models/{model}/"

    # 1. Local relational map (instant, no network) ───────────────────────────
    _load_faiss()   # also triggers _load_model_map
    map_parts = _parts_from_map(model)
    if map_parts:
        category = _model_part_map.get(model, {}).get("category", "")
        return {
            "model_number":     model,
            "url":              url,
            "category":         category,
            "compatible_parts": map_parts,
            "_source":          "local_map",
        }

    # 2. Live PartSelect scrape ────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=STEALTH_HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}")

            soup = BeautifulSoup(resp.text, "html.parser")
            result: dict = {"model_number": model, "url": url, "compatible_parts": []}

            if info := soup.find("div", class_="model-info"):
                result["appliance_info"] = info.get_text(strip=True)[:200]

            for part_div in soup.find_all("div", class_="nf__part", limit=15):
                part_data: dict = {}
                if link := part_div.find("a", href=lambda h: h and "/PS" in str(h)):
                    href = link.get("href", "")
                    if m := re.search(r"PS(\d+)", href):
                        part_data["part_number"] = f"PS{m.group(1)}"
                    part_data["name"] = link.get_text(strip=True)
                if price_el := part_div.find("span", class_="price"):
                    part_data["price"] = price_el.get_text(strip=True)
                if part_data:
                    result["compatible_parts"].append(part_data)

            if not result["compatible_parts"]:
                # 3. FAISS full-text fallback ──────────────────────────────────
                faiss_matches = [
                    {"part_number": p["part_number"], "name": p["name"],
                     "price": p["price"], "brand": p["brand"],
                     "category": p["category"], "image_url": p.get("image_url", ""),
                     "url": p.get("url", ""), "description": p["description"]}
                    for p in _faiss_metadata
                    if model in p.get("compatible_models_str", "")
                ]
                if faiss_matches:
                    result["compatible_parts"] = faiss_matches
                    result["_source"] = "index"
                else:
                    result["note"] = (
                        f"No parts found for model {model} in our database. "
                        "Try searching by symptom or part type instead."
                    )

            return result

    except Exception as e:
        # 3. FAISS full-text fallback on network failure ───────────────────────
        matches = [
            {"part_number": p["part_number"], "name": p["name"],
             "price": p["price"], "brand": p["brand"],
             "category": p["category"], "image_url": p["image_url"],
             "description": p["description"]}
            for p in _faiss_metadata
            if model in p.get("compatible_models_str", "")
        ]
        if matches:
            return {"model_number": model, "compatible_parts": matches, "_source": "index"}

        return {
            "model_number":     model,
            "compatible_parts": [],
            "note": f"No compatible parts found in our database for model {model}. "
                    "Try searching by symptom or part type, or check PartSelect.com directly.",
        }


def manage_cart(
    session_id: str,
    action: str,
    part_number: Optional[str] = None,
    name: Optional[str] = None,
    price: Optional[float] = None,
) -> dict:
    cart = _carts.setdefault(session_id, [])

    if action == "add":
        if not part_number:
            return {"error": "part_number required for add"}
        for item in cart:
            if item["part_number"] == part_number:
                item["quantity"] += 1
                break
        else:
            cart.append({"part_number": part_number, "name": name or part_number, "price": price or 0.0, "quantity": 1})
        action_msg = f"Added {name or part_number} to your cart"
    elif action == "remove":
        if not part_number:
            return {"error": "part_number required for remove"}
        _carts[session_id] = [i for i in cart if i["part_number"] != part_number]
        cart = _carts[session_id]
        action_msg = f"Removed {part_number} from your cart"
    else:
        action_msg = "Here is your current cart"

    total = round(sum(i["price"] * i["quantity"] for i in cart), 2)
    return {"message": action_msg, "items": cart, "total": total, "item_count": len(cart)}


def find_parts_by_symptom(symptom: str, category: Optional[str] = None) -> list:
    """Find parts that fix a specific symptom using the relational symptom map."""
    _load_faiss()
    _load_relational_maps()
    if not _symptom_part_map:
        # Fallback to FAISS search if map unavailable
        return []

    symptom_lower = symptom.lower()
    matched_parts: list[str] = []
    matched_keys: list[str] = []

    for key, ps_list in _symptom_part_map.items():
        parts = key.split("|", 1)
        key_cat = parts[0] if len(parts) > 1 else ""
        key_sym = parts[1].lower() if len(parts) > 1 else parts[0].lower()

        if category and key_cat and key_cat != category:
            continue

        # Match using word-boundary regex to avoid partial-word false positives
        if re.search(rf"\b({'|'.join(re.escape(w) for w in symptom_lower.split() if len(w) > 3)})\b", key_sym):
            matched_keys.append(key)
            matched_parts.extend(ps_list)
        elif symptom_lower in key_sym or key_sym in symptom_lower:
            matched_keys.append(key)
            matched_parts.extend(ps_list)

    if not matched_parts:
        return []

    seen: set[str] = set()
    unique = []
    for ps in matched_parts:
        if ps not in seen:
            seen.add(ps)
            unique.append(ps)

    results = _enrich_parts(unique, limit=8)
    return results


def find_parts_by_type(
    part_type: str,
    category: Optional[str] = None,
    brand: Optional[str] = None,
) -> list:
    """Find parts by component type using the relational part_type map."""
    _load_faiss()
    _load_relational_maps()
    if not _part_type_map:
        return []

    part_type_lower = part_type.lower()
    matched_parts: list[str] = []

    for key, entry in _part_type_map.items():
        parts = key.split("|", 1)
        key_cat  = parts[0] if len(parts) > 1 else ""
        key_type = parts[1].lower() if len(parts) > 1 else parts[0].lower()

        if category and key_cat and key_cat != category:
            continue
        if not (part_type_lower in key_type or key_type in part_type_lower):
            continue

        ps_list = entry.get("parts", []) if isinstance(entry, dict) else list(entry)

        if brand and isinstance(entry, dict):
            entry_brands = [b.lower() for b in entry.get("brands", [])]
            if brand.lower() not in entry_brands:
                continue
            # Filter ps_list to only parts matching the brand in metadata
            if _faiss_metadata:
                brand_set = {
                    p["part_number"]
                    for p in _faiss_metadata
                    if p.get("brand", "").lower() == brand.lower()
                }
                ps_list = [ps for ps in ps_list if ps in brand_set]

        matched_parts.extend(ps_list)

    if not matched_parts:
        return []

    seen: set[str] = set()
    unique = []
    for ps in matched_parts:
        if ps not in seen:
            seen.add(ps)
            unique.append(ps)

    return _enrich_parts(unique, limit=8)


def find_parts_by_brand(brand: str, category: Optional[str] = None) -> list:
    """Find parts for a specific brand using the relational brand_appliance map."""
    _load_faiss()
    _load_relational_maps()
    if not _brand_appliance_map:
        return []

    brand_lower = brand.lower()
    matched_parts: list[str] = []

    for key, entry in _brand_appliance_map.items():
        parts = key.split("|", 1)
        key_brand = parts[0].lower() if parts else ""
        key_cat   = parts[1] if len(parts) > 1 else ""

        if key_brand != brand_lower:
            continue
        if category and key_cat and key_cat != category:
            continue

        ps_list = entry.get("parts", []) if isinstance(entry, dict) else list(entry)
        matched_parts.extend(ps_list)

    if not matched_parts:
        return []

    seen: set[str] = set()
    unique = []
    for ps in matched_parts:
        if ps not in seen:
            seen.add(ps)
            unique.append(ps)

    return _enrich_parts(unique[:200], limit=8)


def get_order(order_id: Optional[str] = None) -> dict:
    """
    Demo-only: returns sample order data.
    Real order lookup requires PartSelect account API integration (out of scope for this demo).
    Claude should always clarify this is example data when presenting it.
    """
    demo_note = (
        "Note: Order lookup is a demo feature showing example data. "
        "For real order status, visit partselect.com/MyOrders or call 1-888-738-4871."
    )
    sample_orders = [
        {
            "order_id": "PS-DEMO-78432",
            "status": "Shipped",
            "tracking_number": "1Z999AA10123456784",
            "carrier": "UPS",
            "estimated_delivery": "3–5 business days",
            "items": [{"part_number": "PS11752778", "name": "Refrigerator Ice Maker Assembly", "price": 98.75}],
            "order_total": 98.75,
            "demo": True,
        },
        {
            "order_id": "PS-DEMO-77891",
            "status": "Delivered",
            "tracking_number": "1Z999AA10123456001",
            "carrier": "UPS",
            "delivered_date": "3 days ago",
            "items": [{"part_number": "PS11748360", "name": "Dishwasher Door Latch", "price": 34.20}],
            "order_total": 34.20,
            "demo": True,
        },
    ]
    if order_id:
        order = next((o for o in sample_orders if o["order_id"] == order_id), None)
        if order:
            return {**order, "demo_note": demo_note}
        return {"error": f"Order {order_id} not found", "demo_note": demo_note}
    return {"recent_orders": sample_orders, "demo_note": demo_note}
