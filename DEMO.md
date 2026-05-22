# PartSelect Chat Agent — Demo Script

**Runtime:** ~6 minutes  
**Setup:** Backend on `http://localhost:8001`, frontend on `http://localhost:3000`

---

## Before you start

- Clear the chat (trash icon, top right) so you open on the Welcome screen
- Have the browser devtools closed — keep the UI clean
- The first query of the session triggers FAISS + model loading (~2 s cold start); subsequent queries are fast

---

## Scene 1 — The problem (30 s)

> "PartSelect has over half a million appliance parts. Most customers arrive knowing their symptom — 'my fridge is leaking' — not a part number. Keyword search fails them completely. This agent understands the problem and maps it directly to the right part."

Point to the Welcome screen. Show the three tabs (All / Refrigerator / Dishwasher). Don't click anything yet.

---

## Scene 2 — Symptom search (90 s)

**Type this exactly:**
```
My GE refrigerator is leaking water from the bottom
```

**What happens:**
1. Status label: *"Finding parts for that symptom…"*
2. Streaming text response explains common causes (door seal, water inlet valve, drain pan)
3. Product cards appear **after** the text — 5–8 parts, each with name, part number, brand, price
4. All parts are real GE refrigerator parts from the scraped index

**Talk through:**
- "The agent picked `find_parts_by_symptom` — a structured lookup against 72 symptom keys built from 6,000 scraped parts, not a keyword search"
- "Cards appear after the explanation — the user always reads context before seeing something to buy"
- "These are real prices and part numbers from archived PartSelect pages"

---

## Scene 3 — Model compatibility (60 s)

**Type this exactly:**
```
What parts are compatible with model 25344352401?
```

**What happens:**
1. Status label: *"Checking model compatibility…"*
2. Claude identifies this as a Kenmore refrigerator
3. Returns up to 21 compatible parts from the local relational map (instant — no network call)

**Talk through:**
- "Model number → `check_model_compatibility` — hits a local map of 10,325 appliance models built from the scraped compatible-models field on each part page"
- "Zero network latency — the answer comes from a pre-built JSON map loaded at startup"
- "A customer just needs to type their model number off the label"

---

## Scene 4 — Add to cart (45 s)

Click **Add to cart** on any part card from Scene 2 or 3.

**What happens:**
1. Cart badge in the header immediately shows **1**
2. Click the cart icon — drawer slides in showing the item, quantity controls, subtotal
3. The cart is also synced on the server side via a `cart_sync` SSE event

**Then ask Claude to add something:**
```
Add that water inlet valve to my cart
```

**What happens:**
1. Status label: *"Updating cart…"*
2. Claude calls `manage_cart` → server updates → `cart_sync` event fires → cart badge updates in real time
3. Claude confirms the addition in text

**Talk through:**
- "Two paths to cart: the UI button (client-only) and asking Claude directly (server-synced). Either way the cart stays consistent"
- "Cart persists across page refreshes via localStorage — close and reopen the tab to show it"

---

## Scene 5 — Part deep-dive (45 s)

**Type this exactly:**
```
Tell me about part PS8746671
```

**What happens:**
1. Status label: *"Fetching part details…"*
2. Agent tries live PartSelect first, falls back to Wayback Machine archive
3. Returns: name (Lower Spray Arm), price ($26.97), 5.0★ rating, 13 reviews, installation info

**Talk through:**
- "Part number → `get_part_details` — live scrape of PartSelect with Wayback Machine as fallback. PartSelect's CDN blocks automated access, so the agent uses the Internet Archive"
- "This is real data: $26.97, 5 stars, 13 reviews"

---

## Scene 6 — Brand search (30 s)

**Type this exactly:**
```
Show me Bosch dishwasher parts
```

**What happens:**
1. Status label: *"Looking up brand parts…"*
2. Returns 8 Bosch dishwasher parts from the brand × appliance relational map

**Talk through:**
- "Brand-only query → `find_parts_by_brand` — a separate map that groups parts by brand and appliance type"
- "Same tool-selection logic handles every query type without any routing code — Claude reasons about intent and picks the right tool"

---

## Scene 7 — Scope guard (15 s)

**Type this exactly:**
```
Can you help me find a part for my microwave?
```

**What happens:**
Claude declines cleanly:
> "I'm specialized in refrigerator and dishwasher parts — I'm not able to help with microwave parts, but I'd be happy to help you find the right part for your appliance!"

**Talk through:**
- "The agent is scoped to refrigerators and dishwashers. The system prompt enforces this — no special routing code, just a rule Claude follows"

---

## Backup queries

If any scene doesn't produce good results, use these alternatives:

| Intent | Backup query |
|--------|-------------|
| Symptom (fridge) | `My refrigerator is not dispensing water` |
| Symptom (dishwasher) | `My dishwasher is not cleaning dishes properly` |
| Model number | `What fits dishwasher model 66512413N412?` |
| Part detail | `What can you tell me about PS732699?` (5★ silverware basket, $38.57) |
| Brand | `I have a Samsung refrigerator, what parts do you carry?` |
| Part type | `I need a replacement door gasket for a GE refrigerator` |

---

## Key talking points (to weave in throughout)

| Point | When to say it |
|-------|---------------|
| **6,025 real parts** scraped from PartSelect via Wayback Machine CDX | Scene 2 |
| **8 tools, thin data accessors** — Claude is the reasoning layer, not a decision tree | Any tool call |
| **SSE streaming** — each word chunk, tool call, and cart update is a typed event; frontend is purely reactive | Scene 4 |
| **Zero external vector DB** — FAISS runs locally, 384-dim all-MiniLM-L6-v2 embeddings, <50 ms per query | Scene 2 or 5 |
| **Parts buffer** — product cards are held until the first text token so context always precedes purchase options | Scene 2 |
| **New appliance category = scrape + re-index** — zero changes to agent code | Wrap-up |

---

## System Design

### The core idea: thin tools, smart agent

The central decision was to make Claude the reasoning layer and keep every tool a minimal data accessor. There is no routing logic, no intent classifier, no decision tree. Claude reads the user's message, picks the right tool from a set of 8, and composes the answer from the result.

```
User message (any form)
        │
        ▼
  Claude claude-sonnet-4-6  ← system prompt + 8 tool definitions
        │
   picks one or more tools
        │
   ┌────┴────────────────────────────────────────────┐
   ▼        ▼           ▼          ▼         ▼       ▼
search   get_part   check_model  find_by_  manage  get_order
catalog  details    compat.      symptom/  cart
                                 type/brand
```

New query types are handled without new code. A new appliance category means scraping and re-indexing — zero changes to agent logic.

---

### Request flow

```
Browser (Next.js)
    │
    │  POST /chat  { messages[], session_id }
    ▼
FastAPI  ──► rate limiter (20 req / 60 s)  ──► session tracker (2 hr TTL)
    │
    ▼
run_agent()  ──►  Claude API  (tool-use loop)
                       │
              ┌────────┴────────────────────┐
              │  Tool result                │  Final text
              ▼                             ▼
         execute_tool()             stream word chunks
              │                     via SSE → browser
         emit SSE events
         (parts / cart_sync)
```

1. The browser POSTs the full message history and a session ID
2. FastAPI checks the rate limit, then hands off to `run_agent()`
3. Claude receives the system prompt, conversation history, and all 8 tool definitions in one API call
4. If Claude returns tool calls, `execute_tool()` runs them and the results are appended to the conversation — the loop continues until Claude returns plain text
5. Text is streamed word-by-word as SSE. Tool results that contain parts or cart state emit their own typed SSE events

---

### Data layer: two-level retrieval

Every query hits at most two layers:

| Layer | What it handles | How |
|-------|----------------|-----|
| **Relational maps** | Structured lookups — model number, symptom, part type, brand | Pre-built JSON loaded at startup, O(1) key lookup |
| **FAISS semantic index** | Vague or general queries | `all-MiniLM-L6-v2` embeddings (384-dim), `IndexFlatIP` cosine similarity, top-5 in <50 ms |
| **Live scrape + Wayback** | Single part deep-dive | Fetch PartSelect page → Wayback Machine fallback for CDN-blocked responses |

The relational maps were built from 6,025 scraped parts and cross-referenced against PartSelect's XML sitemaps (101,843 part URLs, 287,259 model URLs). Semantic search handles vague queries; the maps handle structured ones.

---

### Data sourcing: why Wayback Machine

PartSelect's CDN (Akamai) blocks direct scraping. All part data — names, prices, symptoms, compatible models, ratings — was sourced from the **Internet Archive Wayback Machine**:

- **Discovery:** Wayback CDX API enumerates all archived PartSelect pages
- **Fetching:** Each part fetched as a 2022–2024 snapshot (real HTML with full metadata)
- **Images:** The `/image/{part_number}` proxy endpoint queries CDX for cached part images, bypassing CDN hotlink protection at runtime

---

### SSE event contract

The backend and frontend communicate exclusively through five typed SSE events. The frontend is stateless relative to the agent — it just reacts to events.

| Event | Payload | Frontend effect |
|-------|---------|-----------------|
| `tool_call` | Tool name | Show status label ("Searching catalog…") |
| `text` | Word chunk | Append to assistant message |
| `parts` | `Part[]` | Hold in buffer until first text, then render cards |
| `cart_sync` | `CartItem[]` | Replace entire cart state atomically |
| `done` | — | Record response time, show follow-up chips |

The **parts buffer** is the key UX decision: product cards are withheld until the first text token arrives so the user always reads context before seeing something to buy.

---

### Technology choices

| Layer | Choice | Reason |
|-------|--------|--------|
| AI model | Claude claude-sonnet-4-6 | Best latency/quality ratio for multi-step tool-use loops |
| Backend | FastAPI (Python) | Native async streaming, richest AI/scraping ecosystem |
| Vector search | FAISS (local) | No external dependency, zero cold-start latency, sufficient at 6k vectors |
| Embeddings | all-MiniLM-L6-v2 | Fast, runs locally, strong semantic similarity at 384 dims |
| Frontend | Next.js 14 App Router | SSE streaming, Tailwind co-location, Vercel-deployable |
| HTTP client | httpx (async) | Native async, connection pooling for both scraping and Wayback requests |

---

## High Level Design

### Frontend — Next.js 14 App Router

| Component | Responsibility |
|-----------|----------------|
| `page.tsx` | Root state: messages, cart, session ID, SSE stream handling, parts buffer |
| `MessageBubble.tsx` | Renders assistant/user turns — inline markdown, product card rows, tool status labels |
| `ProductCard.tsx` | Part card: name, part number, brand, rating, price, Add-to-cart, View on PartSelect |
| `CartSidebar.tsx` | Sliding drawer — quantity controls, subtotal, checkout link |
| `WelcomeScreen.tsx` | Greeting, appliance filter tabs, suggestion prompts |
| `ErrorBoundary.tsx` | Catches render errors, shows retry button |
| `api.ts` | `streamChat()` async generator — parses SSE, surfaces 429 Retry-After |

### Backend — FastAPI (Python 3.11+)

| Route | Purpose |
|-------|---------|
| `POST /chat` | Main SSE stream — accepts message history + session ID |
| `GET /health` | Liveness probe |
| `GET /image/{part_number}` | Wayback Machine image proxy, process-level cache |
| `DELETE /cart/{session_id}` | Clear server-side cart |

Middleware: 20 req/60 s sliding rate limit per IP, 2 hr session TTL, configurable CORS, background cleanup every 5 min.

### Agent loop — `claude_client.py`

```
messages[]
    │
    └──► Claude API  (claude-sonnet-4-6, max_tokens=4096)
              │
        ┌─────┴──────┐
        │ tool_uses? │
        └─────┬──────┘
       no ◄───┤───► yes
        │          │
        │     execute_tool()
        │          ├── emit tool_call SSE
        │          ├── emit parts SSE   (search / lookup tools)
        │          └── emit cart_sync SSE  (manage_cart)
        │     append tool_results → loop back to Claude
        │
    stream final text in ~4-char word chunks
    emit done SSE
```

Retry: 2 attempts with 1 s / 3 s backoff on HTTP 429 / 529 from Anthropic.

### 8 tools

| Tool | Trigger | Source | Output |
|------|---------|--------|--------|
| `search_catalog` | General keyword | FAISS index | Top 5 parts |
| `get_part_details` | Part number | Live PartSelect → Wayback | Full part record |
| `check_model_compatibility` | Model number | Relational map → live scrape | Compatible parts |
| `find_parts_by_symptom` | Symptom / problem | symptom_part_map → FAISS | Up to 8 parts |
| `find_parts_by_type` | Component category | part_type_map → FAISS | Up to 8 parts |
| `find_parts_by_brand` | Brand only | brand_appliance_map → FAISS | Up to 8 parts |
| `manage_cart` | Add / remove / view | In-memory session store | Cart state + cart_sync SSE |
| `get_order` | Order ID | Demo fixture | Order record (demo only) |

### Data pipeline (run once to build the index)

```
XML Sitemaps (101,843 part URLs + 287,259 model URLs)
      │
      ▼
build_from_sitemap.py   →  sitemap_parts.json, sitemap_models.json
      │
      ▼
scrape_parts.py         →  parts_raw.jsonl  (6,025 parts, ~3 hrs)
      │
      ▼
build_relational_index.py  →  symptom / type / model / brand maps
      │
      ▼
embed_and_index.py      →  faiss_index.bin + parts_metadata.json
                            → copied to backend/app/data/
```

---

## Design Decisions

### 1. Thin tools, smart agent — not one chain per intent

The rejected approach was to build a dedicated function for every query type (`troubleshoot_appliance`, `get_installation_guide`, etc.). This breaks on queries that weren't anticipated and requires new code for every new intent.

The chosen approach: Claude is the reasoning layer. Tools are minimal data accessors — they return JSON and nothing else. Claude decides how to compose them. A query like "my Whirlpool fridge is leaking and I want to know the install difficulty of the top fix" requires no new code — Claude calls `find_parts_by_symptom` then `get_part_details` in sequence.

### 2. Two-tier retrieval — relational maps first, FAISS second

Structured queries (model number, brand, exact symptom) are answered by pre-built JSON maps with O(1) lookup. Semantic FAISS search is reserved for vague or general queries. This keeps structured results deterministic and fast while still handling natural language inputs well.

FAISS over a hosted vector DB (Pinecone, Weaviate): no external dependency, no API key, no cold-start, sub-50 ms queries at 6k vectors. At this scale, a local IndexFlatIP is faster and simpler than a managed service.

### 3. SSE over WebSocket

Chat is unidirectional (server → client). SSE is simpler than WebSocket for this: it reconnects automatically, works through HTTP proxies and CDNs, and maps directly to a FastAPI `StreamingResponse`. No additional library needed.

### 4. Parts buffer — cards after text, always

Product cards are held in a frontend buffer until the first text token arrives. Without this, cards render before the explanation: the user sees prices before they understand what the parts are or whether they're relevant. The buffer enforces: context first, purchase options second.

### 5. cart_sync SSE — server is authoritative on Claude-managed cart

When the user clicks "Add to cart" on a card, it's a client-side state update only — fast, no round-trip. When Claude calls `manage_cart` (e.g., "add the water inlet valve"), the server emits a `cart_sync` event with the full updated cart. The frontend replaces its state from the server's version. This keeps both paths consistent without a polling loop.

### 6. Wayback Machine as primary data source

PartSelect's CDN (Akamai) blocks direct scraping with aggressive bot detection. The Wayback Machine CDX API provides enumeration of all archived pages and direct access to 2022–2024 snapshots with full HTML — names, prices, symptoms, compatible models, ratings, installation data. The same Wayback proxy is used at runtime for the image endpoint.

### 7. Scope enforcement in the system prompt, not in code

The agent only handles refrigerator and dishwasher parts. This rule lives in the system prompt as a plain instruction: "Only answer questions about refrigerator and dishwasher parts." Claude enforces it. There is no code-level routing, no topic classifier, no allowlist. The rule is easy to change and the agent applies it to edge cases intelligently.

---

## Tech Stack

| Layer | Technology | Version | Why this, not the alternative |
|-------|-----------|---------|-------------------------------|
| AI model | Claude claude-sonnet-4-6 | — | Best latency/quality for multi-step tool-use; streaming API; native tool-use protocol |
| Backend framework | FastAPI | latest | Native async, `StreamingResponse` for SSE, automatic OpenAPI docs, richest Python AI/scraping ecosystem |
| LLM SDK | Anthropic Python SDK | latest | Official SDK; handles tool-use message construction, retries, streaming |
| Vector search | FAISS (`IndexFlatIP`) | 1.7.x | Local, zero dependencies, <50 ms at 6k vectors — no need for Pinecone/Weaviate at this scale |
| Embeddings | all-MiniLM-L6-v2 | — | 384-dim, runs locally via sentence-transformers, strong semantic similarity, no API calls |
| HTTP client | httpx (async) | latest | Native async, connection pooling — used for both Wayback scraping and Anthropic retries |
| HTML parsing | BeautifulSoup4 | latest | Robust parsing of archived PartSelect HTML with inconsistent markup |
| Frontend framework | Next.js 14 App Router | 14.2 | SSE streaming via `fetch` ReadableStream, Tailwind co-location, Vercel-deployable |
| Styling | Tailwind CSS | 3.4 | Utility-first, co-located with components, no CSS file management |
| Icons | Lucide React | 0.344 | Consistent, lightweight, tree-shakeable |
| Runtime | Python 3.11+ / Node 18+ | — | Python 3.11 `asyncio` performance improvements; Node 18 native fetch |

---

## Evaluation Metrics

### Functional correctness

| Metric | How to measure | Target |
|--------|---------------|--------|
| **Tool selection accuracy** | Given a query with a known correct tool (e.g. model number → `check_model_compatibility`), does the agent pick it? | >95% on a labelled eval set of 50 queries |
| **Part relevance** | For symptom and keyword queries, are the returned parts actually relevant to the user's problem? | Human rating ≥4/5 on a 20-query sample |
| **Model compatibility recall** | For a model number in the index, does the response include the known compatible parts? | 100% for models with ≥5 parts in the map |
| **Scope adherence** | Does the agent correctly decline queries outside refrigerator/dishwasher parts? | 100% on a set of 20 off-topic queries |
| **Cart accuracy** | When asked to add a specific part, does the correct part number appear in the cart? | 100% — verifiable from `cart_sync` payload |

### Performance

| Metric | Measurement | Observed |
|--------|-------------|---------|
| **Time to first text token** | From POST /chat to first `text` SSE event | ~2–3 s (includes Claude API round-trip + tool execution) |
| **Total response time** | POST to `done` SSE event | Shown in UI after each response (bottom-left of message) |
| **FAISS query latency** | Time inside `_faiss_index.search()` | <50 ms for k=50 over 6,025 vectors |
| **Relational map lookup** | Time for key lookup in symptom/model/brand maps | <1 ms (in-memory dict) |
| **Wayback image load** | First-load vs. cached via `_img_cache` | First: 2–8 s; cached: <5 ms |
| **Cold start** | First query after backend restart (loads FAISS + ST model) | ~3–5 s |

### Coverage

| Dimension | Count |
|-----------|-------|
| Parts indexed | 6,025 |
| Appliance models mapped | 10,325 |
| Symptom keys | 72 |
| Part type keys | 87 |
| Brand × appliance keys | 77 |
| Top brands | GE (2,912 parts), Whirlpool (1,122), Frigidaire (1,029), Samsung (377), Bosch (284) |

**Known gaps:** Dishwasher parts are 19% of the index (mirrors the sitemap distribution). Rating/install-difficulty data is sparse (~3% of parts). Prices are from 2022–2024 snapshots and not real-time.

### Robustness

| Scenario | Behaviour |
|----------|-----------|
| Anthropic API rate-limited (429) | 2 retries with 1 s / 3 s backoff; user sees error message after exhausting retries |
| Wayback Machine unavailable | `get_part_details` falls back to FAISS metadata; returns partial data with no error |
| Model number not in index | Falls back to live PartSelect scrape; if blocked, returns graceful "not found" message |
| Part number not in index | `get_part_details` attempts live scrape then Wayback; only fails if both are unavailable |
| Client rate-limited (429) | Frontend surfaces `Retry-After` header value in error message |
| History too long (>100 msgs) | Backend returns 400; frontend shows error with retry button |

---

## Architecture in one sentence

> Claude picks the right tool, the tools return structured data, and SSE streams everything — text, parts, and cart state — to a stateless React frontend.
