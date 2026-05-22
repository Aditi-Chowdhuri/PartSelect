# PartSelect Backend

FastAPI backend that runs the Claude claude-sonnet-4-6 agent loop and serves the SSE chat stream.

---

## Setup

```bash
cd backend
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Health check: `GET http://localhost:8001/health` → `{"status": "ok"}`

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Claude API key |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000,http://localhost:3001` | Comma-separated CORS origins |

---

## API routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `POST` | `/chat` | Main chat endpoint — returns SSE stream |
| `GET` | `/image/{part_number}` | Image proxy via Wayback Machine CDX |
| `DELETE` | `/cart/{session_id}` | Clear a session's server-side cart |

### POST /chat

**Request body:**

```json
{
  "messages": [
    {"role": "user", "content": "My Whirlpool fridge ice maker isn't working"}
  ],
  "session_id": "optional-uuid-string"
}
```

**Response:** `text/event-stream` — a sequence of JSON SSE events:

| Event type | Payload | Frontend effect |
|------------|---------|-----------------|
| `tool_call` | Tool name string | Show status label ("Searching catalog…") |
| `text` | Word chunk | Append to assistant message |
| `parts` | `Part[]` | Buffer until first text, then render product cards |
| `cart_sync` | `CartItem[]` | Replace entire frontend cart state |
| `done` | Empty string | Record response time, show follow-up chips |

**Limits:**
- 20 requests per 60-second sliding window per IP (returns 429 with `Retry-After`)
- Maximum 100 messages in history (returns 400 if exceeded)

---

## Agent tools

| Tool | Trigger | Source |
|------|---------|--------|
| `search_catalog` | General keyword query | FAISS vector index |
| `get_part_details` | Specific part number (e.g. PS11752778) | Live PartSelect → Wayback fallback |
| `check_model_compatibility` | Appliance model number (e.g. WDT780SAEM1) | Live PartSelect → relational map |
| `find_parts_by_symptom` | Symptom description (e.g. "not making ice") | symptom map → FAISS |
| `find_parts_by_type` | Part category name (e.g. "door gasket") | part-type map → FAISS |
| `find_parts_by_brand` | Brand name only (e.g. "Samsung") | brand map → FAISS |
| `manage_cart` | Add / remove / view cart items | In-memory session store |
| `get_order` | Order ID | Demo fixture data |

---

## Data files

All data files live in `backend/app/data/` and are loaded at startup:

| File | Description |
|------|-------------|
| `faiss_index.bin` | FAISS IndexFlatIP (6,025 vectors, 384-dim) — gitignored, regenerate with `scraper/embed_and_index.py` |
| `parts_metadata.json` | Full part records keyed by vector index position |
| `model_part_map.json` | 10,325 appliance models → compatible PS numbers |
| `symptom_part_map.json` | 72 "category\|symptom" keys → [PS numbers] |
| `part_type_map.json` | 87 "category\|type" keys → {parts, brands} |
| `brand_appliance_map.json` | 77 "Brand\|appliance" keys → {parts} |

---

## Session and cart lifecycle

- Session TTL: 2 hours of inactivity
- Cart state: stored in `_carts` dict in-process; survives until session eviction or server restart
- Background cleanup task runs every 5 minutes to evict stale sessions and rate-limit buckets

---

## Image proxy

PartSelect's CDN blocks hotlinking. `GET /image/{part_number}` proxies part images through Wayback Machine:

1. Queries Wayback CDX API for cached image snapshots of the part number
2. Tries up to 6 candidate URLs (prefers JPEG, requires >800 bytes)
3. Caches successful responses in process memory for instant repeat loads
