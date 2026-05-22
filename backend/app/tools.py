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
        return True
    except Exception as e:
        print(f"[FAISS] Load failed: {e}")
        return False


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
    result.setdefault("image_url", f"https://www.partselect.com/assets/images/parts/PS{pn}.jpg")

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


async def check_model_compatibility(model_number: str) -> dict:
    model = model_number.strip().upper()
    url   = f"https://www.partselect.com/Models/{model}/"

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
                # Fall back to FAISS metadata — find parts whose compatible_models_str contains this model
                if _load_faiss():
                    faiss_matches = [
                        {"part_number": p["part_number"], "name": p["name"],
                         "price": p["price"], "brand": p["brand"],
                         "category": p["category"], "image_url": p["image_url"],
                         "description": p["description"]}
                        for p in _faiss_metadata
                        if model in p.get("compatible_models_str", "")
                    ]
                    if faiss_matches:
                        result["compatible_parts"] = faiss_matches
                        result["_source"] = "index"

            return result

    except Exception as e:
        # Fall back to FAISS index for compatibility
        if _load_faiss():
            matches = [
                {"part_number": p["part_number"], "name": p["name"],
                 "price": p["price"], "brand": p["brand"],
                 "category": p["category"], "image_url": p["image_url"],
                 "description": p["description"]}
                for p in _faiss_metadata
                if model in p.get("compatible_models_str", "")
            ]
            return {"model_number": model, "compatible_parts": matches, "_source": "index"}

        return {"model_number": model, "compatible_parts": [], "error": str(e)}


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


def get_order(order_id: Optional[str] = None) -> dict:
    sample_orders = [
        {
            "order_id": "PS-2024-78432",
            "status": "Shipped",
            "tracking_number": "1Z999AA10123456784",
            "carrier": "UPS",
            "estimated_delivery": "May 23, 2026",
            "items": [{"part_number": "PS11752778", "name": "Refrigerator Ice Maker Assembly", "price": 98.75}],
            "order_total": 98.75,
        },
        {
            "order_id": "PS-2024-77891",
            "status": "Delivered",
            "tracking_number": "1Z999AA10123456001",
            "carrier": "UPS",
            "delivered_date": "May 18, 2026",
            "items": [{"part_number": "PS11748360", "name": "Dishwasher Door Latch", "price": 34.20}],
            "order_total": 34.20,
        },
    ]
    if order_id:
        order = next((o for o in sample_orders if o["order_id"] == order_id), None)
        return order if order else {"error": f"Order {order_id} not found"}
    return {"recent_orders": sample_orders}
