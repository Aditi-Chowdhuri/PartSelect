# PartSelect Chat Agent — High Level Design

---

## 1. Executive Summary

A conversational AI assistant for PartSelect.com scoped to refrigerator and dishwasher parts. Users describe symptoms, provide model numbers, or ask by brand — the agent finds the right part, explains it, and adds it to cart. Built on a Claude claude-sonnet-4-6 tool-use agent loop with a local FAISS vector index over 6,025 real scraped parts and a set of relational maps cross-referencing models, symptoms, brands, and part types.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (Next.js)                          │
│                                                                   │
│  WelcomeScreen ──► ChatInput ──► MessageBubble ──► ProductCard   │
│                                        │                          │
│                                   CartSidebar                     │
└───────────────────────┬──────────────────────────────────────────┘
                        │  HTTP POST /chat  (SSE stream)
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                        │
│                                                                   │
│  Rate limiter ──► Session manager ──► run_agent()                │
│                                            │                      │
│                              ┌─────────────▼──────────────┐     │
│                              │  Claude claude-sonnet-4-6 Agent Loop  │
│                              │  (Anthropic SDK, tool use)  │     │
│                              └─────────────┬──────────────┘     │
│                                            │                      │
│       ┌──────────────┬─────────────┬───────┴──────┬──────────┐  │
│       ▼              ▼             ▼               ▼          ▼  │
│  search_catalog  get_part_details  check_model  find_by_*  manage│
│  (FAISS + ST)    (live + Wayback)  (live scrape) (maps)    _cart │
└──────────────────────────────────────────────────────────────────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
    FAISS Index    Relational    PartSelect.com /
    (local disk)   Maps (JSON)   Wayback Machine
```

---

## 3. Component Breakdown

### 3.1 Frontend (Next.js App Router, TypeScript, Tailwind CSS)

| Component | Responsibility |
|-----------|----------------|
| `page.tsx` | Root state: messages, cart, session ID, SSE stream handling, parts buffer |
| `MessageBubble.tsx` | Renders assistant/user turns; inline markdown, product card rows, tool status |
| `ProductCard.tsx` | Part card: name, part number, brand, rating, price, Add-to-cart, View link |
| `CartSidebar.tsx` | Sliding drawer; quantity controls, subtotal, checkout to PartSelect |
| `WelcomeScreen.tsx` | Greeting, filter tabs (All/Refrigerator/Dishwasher), suggestion prompts |
| `ErrorBoundary.tsx` | React class component; catches render errors, shows retry button |
| `api.ts` | `streamChat()` async generator; parses SSE events, surfaces 429 Retry-After |

**Key frontend design decisions:**

- **SSE not WebSocket** — chat is unidirectional; SSE is simpler, reconnects automatically, works through proxies
- **Parts buffer** — parts events are held until the first text chunk arrives so the user always reads context before seeing product cards
- **cart_sync event** — when Claude calls `manage_cart`, the backend emits `cart_sync` with the full updated items list; frontend replaces cart state atomically
- **localStorage cart** — cart survives page refresh even if the backend session expires
- **Single accent colour** — gray-900 + brand-orange (#e8651a) only; no blue in product UI

---

### 3.2 Backend (FastAPI, Python 3.11+)

**API Surface**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness probe |
| POST | `/chat` | Main SSE stream; accepts message history + session_id |
| GET | `/image/{part_number}` | Image proxy via Wayback CDX; caches in process memory |
| DELETE | `/cart/{session_id}` | Clear a session's server-side cart |

**Middleware and safety**

| Concern | Implementation |
|---------|---------------|
| Rate limiting | Sliding window: 20 requests / 60 s per IP; returns 429 with `Retry-After` |
| Session TTL | Carts and sessions evicted after 2 hours of inactivity |
| CORS | Origins from `ALLOWED_ORIGINS` env var (comma-separated); localhost default |
| Background cleanup | asyncio task every 5 min evicts stale sessions and rate-limit buckets |
| Input validation | Max 100 messages in history (400 error if exceeded) |
| Image proxy safety | Part number sanitised to digits only before Wayback CDX query |

---

### 3.3 Agent Loop (`claude_client.py`)

```
messages[]
    │
    └──► Claude API (claude-sonnet-4-6, max_tokens=4096)
              │
        ┌─────┴──────┐
        │ tool_uses? │
        └─────┬──────┘
        no ◄──┤──► yes
        │         │
        │    execute_tool()
        │         ├── emit tool_call SSE
        │         ├── emit parts SSE  (for search/lookup tools)
        │         └── emit cart_sync SSE  (for manage_cart)
        │    append tool_results → loop back to Claude
        │
    stream final text in ~4-char word chunks
    emit done SSE
```

**Retry logic** — 2 retries with 1 s / 3 s backoff on HTTP 429 / 529 from Anthropic API.

**SSE event types emitted**

| Type | Payload | Frontend effect |
|------|---------|-----------------|
| `tool_call` | tool name string | Show status label ("Searching catalog…") |
| `text` | word chunk | Append to assistant message content |
| `parts` | Part[] | Buffer until first text, then attach to message |
| `cart_sync` | CartItem[] | Replace entire frontend cart state |
| `done` | empty string | Record response time, show follow-up chips |

---

### 3.4 Tools (8 total)

| Tool | Trigger signal | Data source | Output |
|------|---------------|-------------|--------|
| `search_catalog` | General keyword query | FAISS vector index | Top 5 parts |
| `get_part_details` | Specific part number | Live PartSelect → Wayback fallback | Full part record |
| `check_model_compatibility` | Appliance model number | Live PartSelect → relational map fallback | Compatible parts list |
| `find_parts_by_symptom` | Symptom description | symptom_part_map → FAISS enrichment | Up to 8 parts |
| `find_parts_by_type` | Part category/type name | part_type_map → FAISS enrichment | Up to 8 parts |
| `find_parts_by_brand` | Brand name only | brand_appliance_map → FAISS enrichment | Up to 8 parts |
| `manage_cart` | Add / remove / view cart | In-memory _carts dict | Cart state + cart_sync SSE |
| `get_order` | Order ID | Demo fixture data | Order record (demo only) |

**Tool selection guide** (enforced in system prompt):

```
Model number given   → check_model_compatibility
Part number given    → get_part_details
Symptom described    → find_parts_by_symptom
Part type requested  → find_parts_by_type
Brand name only      → find_parts_by_brand
General search       → search_catalog
```

---

### 3.5 Data Layer

**Vector Index (FAISS)**

| Property | Value |
|----------|-------|
| Embedding model | all-MiniLM-L6-v2 (sentence-transformers) |
| Dimensions | 384 |
| Index type | IndexFlatIP (cosine similarity via L2-normalised vectors) |
| Vectors | 6,025 |
| Text encoded | name + brand + category + symptoms concatenated |

**Relational Maps (JSON, loaded at startup)**

| File | Keys | What it maps |
|------|------|--------------|
| `model_part_map.json` | 10,325 | Appliance model → compatible PS numbers + category |
| `symptom_part_map.json` | 72 | "category|symptom" → [PS numbers] |
| `part_type_map.json` | 87 | "category|type" → {parts[], brands[]} |
| `brand_appliance_map.json` | 77 | "Brand|appliance" → {parts[]} |

**Image Proxy**

PartSelect's CDN blocks hotlinking. The `/image/{part_number}` endpoint:
1. Queries Wayback Machine CDX API for cached image snapshots of that part
2. Tries up to 6 candidate URLs, prefers JPEG, requires >800 bytes
3. Caches successful response in process memory (`_img_cache` dict)

---

## 4. Data Pipeline

```
XML Sitemaps (101,843 part URLs + 287,259 model URLs, stored in xml/)
      │
      ▼
build_from_sitemap.py
  Parses PartDetail XMLs, fetches PTL pages via Wayback for type classification
  → sitemap_parts.json  (15,857 classified parts)
  → sitemap_models.json (287,259 models)
      │
      ▼
scrape_parts.py
  For each part: try live PartSelect page, fallback to Wayback Machine archive
  Parses: name, price, brand, description, rating, review_count,
          symptoms, compatible_models, install_difficulty, install_time, video_url
  Concurrency: 5 workers, 1–2 s delay per request
  → parts_raw.jsonl  (6,025 unique parts, ~3 hrs runtime)
      │
      ▼
build_relational_index.py
  Builds symptom map from part symptom strings
  Builds part-type map from PTL pages + part name keywords
  Enriches model map with compatible_models from scraped data
  → All JSON maps in scraper/data/
      │
      ▼
embed_and_index.py
  Encodes each part with all-MiniLM-L6-v2
  Builds FAISS IndexFlatIP, normalises vectors
  Copies index + all maps → backend/app/data/
```

---

## 5. Data Coverage

| Metric | Count |
|--------|-------|
| Parts indexed (FAISS) | 6,025 |
| Refrigerator parts | 4,866 (80.8%) |
| Dishwasher parts | 1,159 (19.2%) |
| Appliance models | 10,325 |
| Symptom mappings | 72 |
| Part type mappings | 87 |
| Brand × appliance keys | 77 |
| Top brands in sitemap | GE (8,103), Whirlpool (2,664), Frigidaire (1,660), Samsung (1,486), LG (1,307) |

---

## 6. Request Lifecycle (Happy Path)

```
User types: "My Whirlpool fridge ice maker is not working"

 1. Frontend POST /chat  { messages: [...], session_id: "abc" }
 2. Rate limiter: IP check → OK
 3. run_agent() calls Claude: system prompt + messages + 8 tool definitions
 4. Claude picks:  find_parts_by_symptom(symptom="ice maker not working",
                                          category="refrigerator")
 5. Backend → SSE:  { type:"tool_call", content:"find_parts_by_symptom" }
 6. Frontend: shows "Finding parts for that symptom…"
 7. Tool: symptom_part_map lookup → 12 PS numbers → FAISS metadata enrichment
 8. Backend → SSE:  { type:"parts", content:[{PS11738120, $97.80, ...}, ...] }
 9. Frontend: buffers parts (no text received yet)
10. Claude sees results, writes response text
11. Backend → SSE:  { type:"text", content:"Here are..." }  (word by word)
12. Frontend: first text chunk arrives → flush buffered parts, render both
13. User sees: explanation paragraph, then scrollable product cards
14. Backend → SSE:  { type:"done", content:"" }
15. Frontend: record 7.3s response time, show follow-up suggestion chips
```

---

## 7. Security Model

| Threat | Mitigation |
|--------|-----------|
| API key leakage | `.env` in `.gitignore`; never committed to repo |
| Request flooding | 20 req/60 s sliding window; `Retry-After` on 429 |
| Cross-origin abuse | `ALLOWED_ORIGINS` env var; defaults to localhost only |
| Prompt injection via tool results | Tool results are structured JSON, not rendered as instructions |
| Session data leakage | Session IDs are UUIDs; no user PII stored server-side |
| Oversized history | 400 error if >100 messages submitted |

---

## 8. Known Limitations

| Limitation | Detail |
|------------|--------|
| Order lookup is demo-only | No public PartSelect order API; `get_order` returns simulated data with explicit demo flag |
| Cart is in-memory | Server restart clears cart; localStorage provides client-side persistence |
| Dishwasher underrepresented | 19% of indexed parts vs ~21% of PartSelect sitemap; mirrors source data |
| Images via Wayback | PartSelect CDN blocks hotlinking; Wayback images may occasionally 404 |
| Rating/install data sparse | ~3% of parts have ratings; not consistently published on source pages |
| Prices may drift | Scraped at index time; not real-time |

---

## 9. Extensibility

The tool-use agent pattern is intentionally additive. New capabilities require only a new tool definition + dispatch case — no architectural changes.

**Straightforward extensions:**

| Extension | How |
|-----------|-----|
| Repair guide lookup | `get_repair_guide(symptom, brand)` — `repairs.json` already in backend/app/data |
| Part comparison | `compare_parts(pn_a, pn_b)` — call `get_part_details` twice, Claude compares |
| Installation video | Expose `video_url` field already stored in part metadata |
| Expand to washers/dryers | Scrape new category, re-index, add to scope guard in system prompt |
| Persistent cart | Replace `_carts` dict with Redis or a DB; API to Claude unchanged |
| Real-time pricing | Add a `get_live_price(part_number)` tool that scrapes on demand |
| Replace FAISS | Swap `_load_faiss()` internals for Pinecone/Weaviate; Claude API unchanged |

---

## 10. Deployment (Phase 3)

```
Frontend  →  Vercel
              NEXT_PUBLIC_BACKEND_URL=https://api.yourdomain.com

Backend   →  Railway or Render  (Dockerfile or nixpacks auto-detect)
              ANTHROPIC_API_KEY=sk-ant-...
              ALLOWED_ORIGINS=https://yourapp.vercel.app
```

No database migration needed — all data is flat files bundled with the backend image. The FAISS binary and JSON maps are committed to the repo and loaded at startup.
