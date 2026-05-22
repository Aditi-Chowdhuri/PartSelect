# PartSelect Chat Agent — Design

---

## Problem

PartSelect's catalog has hundreds of thousands of parts. Customers arrive knowing their **symptom** or **model number** — not a part number. The site's keyword search fails them: "ice maker not making ice" returns nothing useful. A conversational agent that understands appliance context and maps intent to the right part removes this friction entirely.

**Scope:** Refrigerator and dishwasher parts only. The agent refuses all other queries.

---

## Core Design Principle: Thin Tools, Smart Agent

The central architecture decision was **not** to build one tool per user intent.

| Rejected approach | Why |
|---|---|
| `troubleshoot_appliance(symptom)` | Bakes in assumptions — breaks on any query it wasn't designed for |
| `get_installation_guide(part_number)` | Claude already knows how to explain installation — it just needs data |
| One LangChain chain per flow | Framework overhead, fragile prompt control, not composable |

**Chosen instead:** Claude as the reasoning layer. Tools are thin data accessors. Claude composes them freely to handle any query type — including ones that weren't anticipated at build time.

```
User intent (any form)
        │
        ▼
  Claude claude-sonnet-4-6  (reasons, picks tools, composes answer)
        │
   ┌────┴─────────────────────────────────────────┐
   ▼        ▼           ▼          ▼         ▼    ▼
search   get_part   check_model  find_by_  manage get_order
catalog  details    compat.      symptom/  cart
                                 type/brand
```

New intents are handled without new code. Adding a new appliance category means scraping + re-indexing — zero changes to agent logic.

---

## Architecture

### Request flow

```
Browser (Next.js)
    │
    │  POST /chat  { messages[], session_id }
    ▼
FastAPI  ──► rate limiter (20 req/60 s)  ──► session tracker (2 hr TTL)
    │
    ▼
run_agent()  ──►  Claude API  (tool use loop)
                       │
              ┌────────┴──────────────────┐
              │  Tool result              │  Final text
              ▼                           ▼
         execute_tool()            stream word chunks
              │                    via SSE → browser
         emit SSE events
         (parts / cart_sync)
```

### SSE event contract

The backend and frontend communicate exclusively through typed SSE events. This makes the frontend stateless relative to the agent — it just reacts to events.

| Event | Payload | Effect |
|-------|---------|--------|
| `tool_call` | tool name | Show status label in chat |
| `text` | word chunk | Stream into assistant message |
| `parts` | Part[] | Buffer until first text, then render cards |
| `cart_sync` | CartItem[] | Replace frontend cart state |
| `done` | — | Show response time + follow-up chips |

**Parts buffer:** product cards are held until the first text token arrives. The user always reads context before seeing purchase options.

**Cart sync:** when Claude calls `manage_cart`, the server emits the full updated cart over SSE. The frontend never needs to poll — it just applies the delta.

---

## Data Strategy

### Two-layer retrieval

| Layer | When used | How |
|-------|-----------|-----|
| **FAISS semantic index** | All catalog queries | Embeddings via `all-MiniLM-L6-v2`, `IndexFlatIP`, cosine similarity |
| **Relational maps** | Structured lookups (model, symptom, type, brand) | Pre-built JSON maps, exact key lookup + FAISS enrichment |
| **Live scrape** | Single part deep-dive | Fetch PartSelect page → Wayback Machine fallback |

Semantic search handles vague queries ("something for my leaking fridge"). Relational maps handle structured queries ("what fits WDT780SAEM1"). Live scrape provides fresh specs and install info on demand without re-indexing.

### Data sourcing — Wayback Machine

PartSelect's CDN and edge protection (Akamai) block direct scraping. Real data is sourced via the **Internet Archive Wayback Machine**:

- **Discovery:** Wayback CDX API enumerates all archived PartSelect part pages
- **Fetching:** Each part page fetched as a 2022–2024 snapshot — real HTML with names, prices, descriptions, compatible models, symptoms, and ratings
- **Image proxy:** The `/image/{part_number}` API endpoint queries CDX for cached part images, serving them through the backend to bypass CDN hotlink protection

### Catalog coverage

| Metric | Count |
|--------|-------|
| Parts indexed | **6,025** |
| Refrigerator | 4,866 (80.8%) |
| Dishwasher | 1,159 (19.2%) |
| Appliance models | **10,325** |
| Symptom mappings | 72 |
| Part type mappings | 87 |
| Brand × appliance | 77 |
| Top brands | GE · Whirlpool · Frigidaire · Samsung · LG · Bosch |

---

## Tool Design

8 tools, each a minimal data accessor:

| Tool | Trigger | Source |
|------|---------|--------|
| `search_catalog` | General keyword or vague query | FAISS index |
| `get_part_details` | Specific part number | Live scrape + Wayback |
| `check_model_compatibility` | Appliance model number | Live scrape + model map |
| `find_parts_by_symptom` | Problem description | Symptom map → FAISS |
| `find_parts_by_type` | Part category name | Part-type map → FAISS |
| `find_parts_by_brand` | Brand name only | Brand map → FAISS |
| `manage_cart` | Add / remove / view | In-memory session store |
| `get_order` | Order ID | Demo fixture (documented) |

The system prompt gives Claude a single rule for tool selection:

> Model number → `check_model_compatibility` · Part number → `get_part_details` · Symptom → `find_parts_by_symptom` · Part type → `find_parts_by_type` · Brand only → `find_parts_by_brand` · Everything else → `search_catalog`

---

## Frontend

### Design decisions

**No chat bubbles for the assistant.** Text flows directly on white, matching Claude.ai's aesthetic. User messages use a gray pill. This avoids visual noise when responses are long.

**Cards after text, always.** The parts buffer ensures product cards never appear before the explanation. Users read context first, then decide.

**One accent colour.** Gray-900 for UI chrome, brand-orange (#e8651a) for the single CTA (Add to cart, cart badge, checkout). No blue in the product flow.

**No images.** PartSelect's CDN blocks hotlinking and the Wayback proxy adds latency. Cards are text-only: name, part number, brand, rating, price. Clean and fast.

### Cart architecture

Cart state lives in two places simultaneously:

| Store | Scope | Purpose |
|-------|-------|---------|
| React state (`cartItems`) | Session | Drives all UI rendering |
| `localStorage` | Browser | Survives page refresh |
| Backend `_carts` dict | Server session | Authoritative when Claude manages cart |

On `cart_sync` SSE, React state is replaced with the server's version. On page load, React state is seeded from localStorage. The three stay consistent through normal use.

---

## Technology Choices

| Layer | Choice | Key reason |
|-------|--------|-----------|
| AI model | Claude claude-sonnet-4-6 | Best latency/quality ratio for tool-use loops |
| Backend | FastAPI (Python) | Native async streaming, richest AI/scraping ecosystem |
| Vector search | FAISS (local) | No external dependency, zero latency, sufficient at this scale |
| Frontend | Next.js 14 (App Router) | SSE streaming, Vercel deployment, Tailwind co-location |
| Embeddings | all-MiniLM-L6-v2 | Fast, runs locally, strong semantic similarity at 384 dims |
| HTTP client | httpx (async) | Native async, connection pooling, used for both scraping and Wayback |

---

## What's Next

| Extension | Effort | How |
|-----------|--------|-----|
| Washing machines / dryers | Low | Scrape new category + re-index; zero agent code changes |
| Real-time pricing | Low | Add `get_live_price(pn)` tool — scrapes on demand |
| Repair guide lookup | Low | `repairs.json` already in backend — one new tool |
| Persistent cart | Medium | Replace `_carts` dict with Redis; API to Claude unchanged |
| Multimodal input | Medium | User photos of broken parts → Claude Vision identifies part |
| Personalization | High | Remember user's appliance models across sessions |
