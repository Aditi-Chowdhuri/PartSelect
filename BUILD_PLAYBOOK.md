# Conversational AI Agent — Senior Build Playbook
# Based on: PartSelect Chat Agent Architecture

Full prompt sequence to build, audit, and ship a production-grade AI agent.
Every prompt is copy-paste ready. Replace [BRACKETED] values before pasting.
Parallel agent steps are marked — open additional Claude sessions and run simultaneously.

---

## HOW TO USE THIS PLAYBOOK

There are four types of prompts:
- **PLAN** — PM-level: requirements, architecture, prioritization. Run before writing any code.
- **BUILD** — Engineer-level: implement a specific component.
- **AUDIT** — Senior engineer review: read the code, find issues, fix them.
- **PARALLEL** — Run this in a separate Claude session simultaneously with the adjacent prompt.

Read all PLAN prompts first. Do not skip them. They take 20 minutes total and prevent 2 hours of rework.

---

## VARIABLES — Fill These In Before Starting

| Variable | PartSelect Example | Your Value |
|----------|-------------------|------------|
| [PROJECT_NAME] | partselect-agent | |
| [DOMAIN] | appliance parts | |
| [DATA_SOURCE] | PartSelect.com | |
| [ENTITY] | part | |
| [ENTITIES] | parts | |
| [SCOPE] | refrigerators and dishwashers | |
| [CATEGORY_1] | refrigerator | |
| [CATEGORY_2] | dishwasher | |
| [BRAND_COLOR] | #e8651a | |
| [PRIMARY_USER] | appliance repair customer | |
| [BUSINESS_GOAL] | help customers find and buy the right part | |
| [CART_URL] | partselect.com/shopping-cart/ | |

---

## PHASE 0 — PLAN: PM REQUIREMENTS (Run before any code. 15 minutes.)

### PROMPT P1 — Product Requirements Document

```
Act as a senior product manager. Write a complete PRD for [PROJECT_NAME].

Context: [PROJECT_NAME] is a conversational AI agent that helps [PRIMARY_USER] with [BUSINESS_GOAL] on [DATA_SOURCE]. It is scoped to [SCOPE].

Write the PRD with these sections:

1. PROBLEM STATEMENT
   - What the user cannot do today with [DATA_SOURCE]'s existing search
   - What a [PRIMARY_USER] actually knows when they arrive (symptom, not part number)
   - Business cost of the current gap (abandonment, wrong purchases, support calls)

2. USER PERSONAS
   Define 3 personas with name, goal, what they know, what they do not know:
   - Primary: [PRIMARY_USER] who knows the symptom
   - Secondary: [PRIMARY_USER] who has a model number
   - Power user: technician or pro who knows the part number

3. USER STORIES (MoSCoW priority)
   Must Have:
   - As a [persona], I want to [action] so that [outcome]
   Write 5 Must Have stories.
   Should Have: 3 stories.
   Could Have: 2 stories.
   Will Not Have (this version): 2 explicit exclusions.

4. SUCCESS METRICS
   Define exactly how you will measure success. For each metric:
   - What it measures
   - How to instrument it
   - What good looks like (target value)
   Write 5 metrics covering: task completion, accuracy, performance, scope adherence, user satisfaction.

5. SCOPE BOUNDARY
   List exactly what the agent will and will not answer.
   For out-of-scope queries: what should it say? Write the exact decline message.

6. ACCEPTANCE CRITERIA
   For the MVP to be considered done:
   - List 8 specific, testable criteria
   - Each criterion must be a binary pass/fail

Save this as REQUIREMENTS.md at the project root.
```

---

### PROMPT P2 — Architecture Decision Record

```
Act as a principal engineer. Write a complete architecture decision record for [PROJECT_NAME].

For each decision below, write: the options considered, the decision made, and the reasoning. Be specific — cite latency numbers, cost numbers, or maintenance tradeoffs.

DECISIONS TO DOCUMENT:

1. AI Framework
   Options: LangChain agent, custom tool-use loop, OpenAI function calling, LlamaIndex
   Decision: [choose and justify]
   Consider: how many lines of code, what breaks when the API changes, debugging transparency

2. Vector Search
   Options: FAISS (local), Pinecone, Weaviate, pgvector, ChromaDB
   Decision: [choose and justify]
   Consider: setup time, cost at 10k records, latency, dependency complexity

3. Embedding Model
   Options: OpenAI text-embedding-3-small, all-MiniLM-L6-v2 (local), BGE-small
   Decision: [choose and justify]
   Consider: cost per embed, inference latency, dimension size, CPU vs GPU requirement

4. Streaming Approach
   Options: SSE (server-sent events), WebSocket, polling
   Decision: [choose and justify]
   Consider: HTTP/2 compatibility, reconnection handling, Railway/Vercel proxy behavior, implementation complexity

5. Data Storage
   Options: SQLite, Postgres, MongoDB, DynamoDB, flat JSON files
   Decision: [choose and justify]
   Consider: query patterns needed, migration path, hosting cost, concurrent access

6. Frontend State Management
   Options: Redux, Zustand, Jotai, React Context + useReducer, useState only
   Decision: [choose and justify]
   Consider: cart sync with SSE events, localStorage persistence, bundle size

7. Scraping Approach
   Options: Direct HTTP + BeautifulSoup, Playwright, API reverse engineering (DevTools), Wayback Machine CDX API
   Decision: [choose and justify]
   Consider: CDN blocking, rate limiting, data freshness, legal/ToS compliance

8. Deployment
   Options: Railway + Vercel, Fly.io + Vercel, AWS EC2 + S3, Render, Heroku
   Decision: [choose and justify]
   Consider: Docker support, free tier, cold start, always-on, cost at demo scale

Save as ARCHITECTURE.md at the project root.
Write a summary table at the top: Decision | Choice | Key Reason (one line each).
```

---

### PROMPT P3 — System Design and Data Model

```
Act as a senior systems engineer. Produce the full system design for [PROJECT_NAME].

SECTION 1 — SYSTEM DIAGRAM
Draw an ASCII architecture diagram showing every component and how they connect:
- Browser (Next.js frontend)
- FastAPI backend (routes, middleware, rate limiter, session manager)
- Agent loop (Claude tool-use)
- 8 tools and what data source each hits
- SSE stream direction
- Data files loaded at startup
- Scraper pipeline (offline, not part of request path)

Label every arrow with the protocol and data format (e.g. "HTTP POST JSON", "SSE text/event-stream", "FAISS cosine search").

SECTION 2 — DATA FLOW
Write a numbered step-by-step trace for this exact request: "My GE refrigerator is leaking water"
From browser click → SSE stream complete. Include every function call, every data lookup, every SSE event emitted. Be specific about latencies at each step.

SECTION 3 — DATA MODEL
For each data file the system uses, specify:
- Filename
- Format (JSON array / JSON dict / binary)
- Key structure (for maps: what is the key, what is the value)
- Approximate size at demo scale
- How it is built (which scraper script, which step)
- How it is loaded (at startup / per request / cached)

SECTION 4 — API CONTRACT
Document every API endpoint:
Method | Path | Request body / query params | Response shape | Status codes | Notes

SECTION 5 — SCALABILITY ANALYSIS
For each of these scale scenarios, describe what breaks first and how to fix it:
- 10x more data (60,000 [entities] instead of 6,000)
- 100 concurrent users
- Adding 3 more [SCOPE] categories
- Daily data refresh requirement

Save as DESIGN.md at the project root.
```

---

## PHASE 1 — BUILD: SCAFFOLD + DATA

### PROMPT B1 — Project Scaffold

```
Create the full project scaffold for [PROJECT_NAME]. Use the architecture and design decisions from ARCHITECTURE.md and DESIGN.md.

Stack:
- Backend: FastAPI (Python 3.11), async, SSE streaming
- AI: Anthropic claude-sonnet-4-6, native tool-use loop (no LangChain)
- Frontend: Next.js 14 App Router, TypeScript, Tailwind CSS
- Search: FAISS IndexFlatIP + all-MiniLM-L6-v2 embeddings
- Scraper: Python httpx + asyncio + BeautifulSoup4

Create this directory structure with all files as empty stubs:

[PROJECT_NAME]/
  backend/
    app/
      __init__.py
      main.py
      models.py
      tools.py
      claude_client.py
    data/
    requirements.txt
    .env
    .env.example
    Dockerfile
    .dockerignore
  frontend/
    src/
      app/
        page.tsx
        layout.tsx
        globals.css
      components/
        ChatInterface.tsx
        MessageBubble.tsx
        ProductCard.tsx
        CartSidebar.tsx
        WelcomeScreen.tsx
        ToolCallIndicator.tsx
      lib/
        api.ts
        types.ts
        store.ts
    package.json
    tailwind.config.ts
    next.config.ts
    .env.local
    .env.local.example
  scraper/
    scrape_data.py
    build_index.py
    embed_and_index.py
  REQUIREMENTS.md   (from P1)
  ARCHITECTURE.md   (from P2)
  DESIGN.md         (from P3)
  README.md

Steps:
1. cd frontend && npx create-next-app@latest . --typescript --tailwind --app --yes
2. cd backend && pip install fastapi uvicorn anthropic sentence-transformers faiss-cpu httpx beautifulsoup4 python-dotenv numpy pydantic
3. Write backend/requirements.txt with all packages pinned to current versions
4. Write frontend/tailwind.config.ts extending colors with brand-[PROJECT_NAME]: "[BRAND_COLOR]"

Confirm every file and directory exists. Print the full tree.
```

---

### PROMPT B2 — Scraper (START THIS FIRST — it takes 30-45 minutes)

```
Build the data scraper in scraper/scrape_data.py for [PROJECT_NAME].

SCRAPING APPROACH:
[PASTE ONE OF THESE BASED ON WHAT YOU FOUND IN DEVTOOLS — delete the others]

--- API APPROACH (found an API call in DevTools Network tab) ---
Here is the cURL command I captured:
[PASTE FULL CURL]
Here is a sample response:
[PASTE RAW JSON]
Pagination: [field name and logic]

--- SITEMAP APPROACH ---
Sitemap URL: [URL]
Entity URL pattern: [pattern]
Fields to extract from each page: [list]

--- BEAUTIFULSOUP APPROACH ---
Page URL: [URL pattern]
HTML selectors: [describe structure]

--- WAYBACK MACHINE APPROACH (when direct access is blocked) ---
The target site blocks automated access. Use the Wayback Machine CDX API.
CDX endpoint: http://web.archive.org/cdx/search/cdx
Params: url=[DOMAIN]/[PATH]*, output=json, fl=original,timestamp,statuscode, filter=statuscode:200, collapse=urlkey, limit=50000
Fetch archived pages: http://web.archive.org/web/[timestamp]/[original_url]
Parse HTML from archived snapshots with BeautifulSoup.

REQUIREMENTS (apply to all approaches):
1. CLI: --zip [VALUE] --radius [MILES] or equivalent territory param
2. Async with httpx.AsyncClient, semaphore(5) concurrent requests
3. Retry: 3 attempts, backoff 2s / 6s / 18s. On 429: wait 60s.
4. Parse each record into a dict with fields: [LIST YOUR FIELDS]
5. Save all records to scraper/data/raw.json as a JSON array
6. Log data quality issues per record to scraper/data/quality_issues.json
7. tqdm progress bar
8. Final print: X scraped, Y failed, Z quality issues

Run as: python scrape_data.py [--zip 10013] [--force]
```

---

## PHASE 1 PARALLEL — Run B3 and B4 simultaneously while B2 scrapes

### PROMPT B3 — Relational Maps (PARALLEL with B4)

```
Build the relational index in scraper/build_index.py for [PROJECT_NAME].

Input: scraper/data/raw.json

Build and save these JSON files to scraper/data/:

1. entities_by_id.json
   Dict: source_id → full record dict

2. symptom_map.json
   Dict: "[category]|[normalized_symptom]" → [list of entity IDs]
   Normalize: lowercase, remove punctuation, collapse whitespace, strip
   Only include keys with 4+ chars after normalization
   Source: each record's symptoms array

3. type_map.json
   Dict: "[category]|[part_type]" → {"parts": [IDs], "brands": [brands], "count": int}
   Classify by keyword matching on entity name:
   [LIST YOUR KEYWORD→TYPE MAPPINGS, e.g. "ice maker" → "ice makers", "door gasket" → "door gaskets"]

4. model_map.json
   Dict: model_number → {"parts": [IDs], "category": str}
   Source: each record's compatible_models array

5. brand_map.json
   Dict: "[brand]|[category]" → [list of entity IDs]

After building, print summary:
- Total entities
- Symptom map: X keys, Y total part references
- Type map: X keys
- Model map: X models
- Brand map: X combinations
```

---

### PROMPT B4 — FastAPI Backend + Tools (PARALLEL with B3)

```
Build the complete FastAPI backend for [PROJECT_NAME].

FILE 1 — backend/app/tools.py:

Load all data files at module level (once at import, not per request):
_DATA_DIR = Path(__file__).parent / "data"
Load: faiss_index (faiss.read_index), parts_metadata (json list), symptom_map, type_map, model_map, brand_map
Load embedding model: SentenceTransformer("all-MiniLM-L6-v2")

Implement 8 tools:

search_catalog(query, category=None, brand=None) → list
  Embed query, normalize vector, FAISS search top 10, filter by category/brand

get_[entity]_details(id: str) → dict
  Try live fetch from [DATA_SOURCE] first
  On failure: fetch from Wayback Machine archive
  Parse HTML, return full details dict
  On total failure: return {"error": "not found"}

check_model_compatibility(model_number: str) → dict
  Look up in model_map
  Return {"model": str, "category": str, "compatible_parts": [full metadata dicts]}
  If not in map: try live scrape, return {"error": "not found"} if both fail

find_parts_by_symptom(symptom: str, category=None) → list
  Normalize symptom, fuzzy match against symptom_map keys (substring match)
  Aggregate and deduplicate matching part IDs
  Return up to 15 full metadata dicts

find_parts_by_type(part_type: str, category=None, brand=None) → list
  Match against type_map keys, filter, return up to 15 dicts

find_parts_by_brand(brand: str, category=None) → list
  Match against brand_map, return up to 20 dicts

manage_cart(session_id: str, action: str, part_number=None, name=None, price=None) → dict
  _carts: dict[str, list] at module level
  Actions: add (append or increment qty), remove, view, clear
  Always return {"items": [...], "total": float, "count": int}

get_order(order_id=None) → dict
  Return message directing to [DATA_SOURCE] order tracking

Also write TOOL_DEFINITIONS list for Anthropic API tool_use.
Each tool: name, description (when Claude should call it), input_schema.

FILE 2 — backend/app/claude_client.py:

SYSTEM_PROMPT: assistant for [DATA_SOURCE] specializing in [SCOPE]
Include explicit tool selection guide (one line per tool: "if user gives X → call Y")
Scope boundary: decline everything outside [SCOPE] with: "I'm specialized in [SCOPE] — I can't help with [topic], but I'd be happy to help you find the right [ENTITY] for your appliance."

run_agent(messages: list, session_id: str) → AsyncGenerator[str, None]:
  client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
  Loop:
    Call client.messages.create (not streaming — tool-use loop)
    Parse content blocks → text_content, tool_uses
    If tool_uses: yield SSE tool_call events, execute tools via asyncio.gather, yield parts/cart_sync events, append to conversation, continue loop
    If no tool_uses: stream text in word chunks, yield done event, return
  Retry 429/529 with delays [1, 3] seconds
  Outer except: yield error SSE, yield done SSE, return

_normalise_part(p) → dict: consistent shape for frontend
_sse(payload) → str: "data: {json}\n\n"
_stream_text(text) → Generator: buffer ~4 chars, yield word-boundary chunks

FILE 3 — backend/app/main.py:

Rate limiter: 20 req/60s sliding window per IP using X-Forwarded-For
CORSMiddleware: origins from ALLOWED_ORIGINS env var
POST /chat → StreamingResponse(run_agent(...), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
GET /health → {"status":"ok"}
GET /image-proxy?url= → proxy [DATA_SOURCE] images through Wayback CDN, validate domain
init_db equivalent: confirm data files exist on startup, log counts

FILE 4 — backend/app/models.py:
ChatMessage, ChatRequest, CartItem Pydantic models
```

---

### AUDIT A1 — Backend Code Review (Run after B4, PARALLEL with B5)

```
Act as a senior software engineer performing a code review of the [PROJECT_NAME] backend.

Read every file in backend/app/ and audit for:

CORRECTNESS:
- Are all 8 tools returning the right shape? Check against TOOL_DEFINITIONS input_schema.
- Does the agent loop handle the case where Claude returns text AND tool_use in the same response?
- Does manage_cart correctly handle duplicate part_number (should increment quantity, not add duplicate)?
- Does the rate limiter use X-Forwarded-For correctly when behind Railway's proxy?
- Does the image proxy validate the URL domain to prevent SSRF?
- Is ANTHROPIC_API_KEY checked at startup with a clear error if missing?

PERFORMANCE:
- Are all data files loaded once at module level, not per request?
- Is the FAISS index loaded once, not reloaded per search?
- Is the embedding model loaded once, not reloaded per search?
- Are tool executions in the agent loop using asyncio.gather (parallel) not sequential awaits?

SECURITY:
- Is ALLOWED_ORIGINS validated against a whitelist pattern?
- Does the image proxy prevent open redirect (only allow known domains)?
- Are there any os.system() or subprocess calls with user input?
- Is raw_json stored safely (no eval, no exec on stored data)?

ROBUSTNESS:
- Does every tool catch exceptions and return {"error": str(e)} rather than raising?
- Does the agent loop have an outer try/except that catches any uncaught exception and yields a clean error SSE?
- Does the SSE stream always end with a "done" event, even on error?

For each issue found: file path, line number (estimate), description of the bug, exact fix.
Apply all fixes. Print a summary of what was changed.
```

---

## PHASE 2 — BUILD: FAISS INDEX + FRONTEND (Run after B2 scraping finishes)

### PROMPT B5 — FAISS Vector Index

```
Build the FAISS indexer in scraper/embed_and_index.py for [PROJECT_NAME].

Input: scraper/data/raw.json

Steps:
1. Load all records from raw.json
2. Build embedding text per record: "[name] [category] [brand] [description] [symptoms joined with space]" — max 512 tokens
3. Load SentenceTransformer("all-MiniLM-L6-v2") — 384 dimensions, CPU only
4. Embed in batches of 64 with show_progress_bar=True
5. Normalize all vectors: v = v / np.linalg.norm(v, axis=1, keepdims=True)
6. Build IndexFlatIP (inner product on normalized = cosine similarity)
7. Add all vectors
8. faiss.write_index(index, "scraper/data/faiss_index.bin")
9. Build metadata list — same order as FAISS index. For each record keep only frontend-needed fields:
   id, name, price, brand, category, image_url, url, rating, review_count, symptoms (first 5), install_difficulty, install_time, video_url, description (truncated 300 chars)
   Save as scraper/data/parts_metadata.json

10. Copy to backend/app/data/:
    faiss_index.bin, parts_metadata.json, symptom_map.json, type_map.json, model_map.json, brand_map.json

Print: total vectors, index size on disk, files copied.
Run as: python embed_and_index.py
```

---

### PROMPT B6 — Frontend Types, API Client, State (PARALLEL with B7)

```
Build the frontend foundation for [PROJECT_NAME].

frontend/src/lib/types.ts:

type ApplianceFilter = "all" | "[CATEGORY_1]" | "[CATEGORY_2]"

interface Part {
  part_number: string; name: string; price: number; brand: string; category: string
  image_url: string; url: string; description: string; rating: number; review_count: number
  availability: string; symptoms: string[]; install_difficulty: string; install_time: string; video_url: string
}

interface CartItem { part_number: string; name: string; price: number; quantity: number }

interface Message {
  id: string; role: "user" | "assistant"; content: string
  parts?: Part[]; error?: string; isStreaming?: boolean
  toolCall?: string; timestamp: number; responseTimeMs?: number
}

type SSEEventType = "text" | "parts" | "cart_sync" | "tool_call" | "done" | "error"
interface SSEEvent { type: SSEEventType; content: string | Part[] | CartItem[] }

frontend/src/lib/api.ts:
const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL
— never append trailing slash — causes //chat 404

async function* streamChat(messages, sessionId): AsyncGenerator<SSEEvent>
  POST ${BACKEND}/chat, body: {messages:[{role,content}], session_id}
  Read as ReadableStream, TextDecoder
  Parse SSE: lines starting "data: " → JSON.parse → yield SSEEvent
  On any error: yield {type:"error", content: error.message}

function getImageUrl(url): string → ${BACKEND}/image-proxy?url=${encodeURIComponent(url)}

frontend/src/lib/store.ts:
Cart state via React Context + useReducer. No external library.
State: { items: CartItem[], sessionId: string }
Actions: SET_CART (replace entire cart — called on cart_sync SSE), CLEAR_CART
sessionId: crypto.randomUUID() once, persisted in localStorage key "[PROJECT_NAME]-session"
items: persisted in localStorage key "[PROJECT_NAME]-cart", restored on mount
Export: CartProvider, useCart()
```

---

### PROMPT B7 — All React Components (PARALLEL with B6)

```
Build all React components for [PROJECT_NAME].

WelcomeScreen.tsx:
Props: onSelect(query), filter: ApplianceFilter, onFilterChange(f)
Layout: centered max-w-xl py-12, fade-in animation
- Brand icon in [BRAND_COLOR] square + h1 "[PROJECT_NAME] Assistant" + subtitle
- Filter tab bar (underline active style): All | [CATEGORY_1] | [CATEGORY_2]
- 4 suggestion chips per filter in 2-column grid. Each: label bold + query preview small gray line-clamp-1
- Capabilities list: 5 items with lucide-react icons

QUERIES — use only queries that return real data from the index:
all: 4 verified queries
[CATEGORY_1]: 4 verified queries
[CATEGORY_2]: 4 verified queries

ToolCallIndicator.tsx:
Props: toolName: string
Small pill with animated spinner. Map tool names to human labels:
search_catalog → "Searching catalog"
get_[entity]_details → "Looking up [entity]"
check_model_compatibility → "Checking compatibility"
find_parts_by_symptom → "Finding parts by symptom"
find_parts_by_type → "Browsing part types"
find_parts_by_brand → "Browsing by brand"
manage_cart → "Updating cart"

ProductCard.tsx:
Props: part: Part, onAddToCart(part)
White card, border-gray-200, rounded-xl
- Image: getImageUrl(), h-40, object-cover, gray-100 bg fallback
- name (font-medium), part_number (text-xs text-gray-400), price (font-bold text-[BRAND_COLOR])
- brand + category small badges (gray-100 bg)
- Rating: filled/empty stars + review count (if rating > 0)
- Install difficulty badge (if present)
- "Add to cart" button: full width, [BRAND_COLOR] bg, white text
- "View part" link: text-xs text-gray-400 hover:text-[BRAND_COLOR]

CartSidebar.tsx:
Props: isOpen, onClose
Fixed right panel, backdrop overlay, slide-in transition
Header: "Cart" + badge + X close
Item list: name, part_number, qty, price, remove button (×)
Footer: subtotal bold, "Checkout on [DATA_SOURCE]" button → [CART_URL]
Empty state: gray message

MessageBubble.tsx:
Props: message: Message
User: right-aligned, gray-100, rounded-2xl, max-w-[80%]
Assistant: left-aligned with avatar icon, white bg
  isStreaming + no content: show ToolCallIndicator(toolCall) or pulsing dots
  content: render text (blinking cursor if isStreaming)
  parts array: 2-col ProductCard grid below text
  error: red border, error icon, "Try again" button that re-submits last message
  footer: responseTimeMs + "s" in tiny gray text
```

---

### AUDIT A2 — Frontend Component Review (Run after B6 + B7, PARALLEL with B8)

```
Act as a senior frontend engineer reviewing [PROJECT_NAME] components.

Read all files in frontend/src/ and audit for:

CORRECTNESS:
- Does the SSE stream parser handle partial chunks correctly? (ReadableStream can split a "data: ..." line across two chunks — the parser must buffer incomplete lines)
- Does streamChat yield a final "done" event even if the backend sends no done event? (Add a timeout fallback)
- Does manage_cart in CartSidebar handle quantity > 1 display? (show "×2" not two separate items)
- Does ProductCard use getImageUrl() for all image src values? (not the raw URL which will be blocked by CORS)
- Does WelcomeScreen actually disappear after the first message? (check the empty state condition)
- Is sessionId stable across re-renders? (must come from localStorage, not useState with initial value)

PERFORMANCE:
- Are ProductCard images lazy-loaded? (add loading="lazy")
- Is the message list virtualized or is it just a growing DOM? (for demo it's fine, note the limitation)
- Does the messages area scroll to bottom on new content? (useEffect with ref.scrollIntoView)
- Are components that don't need to re-render wrapped in memo()?

DESIGN CONSISTENCY:
- Is any color class in the codebase NOT in [gray-*, BRAND_COLOR, white, red/amber/green for status]? If yes, remove it.
- Are there any emoji characters in component output? Remove them.
- Is the font stack system-only (no Google Fonts import)?

ACCESSIBILITY:
- Do all buttons have aria-label when they have no text (icon-only buttons)?
- Does the textarea have a placeholder and aria-label?
- Are cart items announced to screen readers when added?

For each issue: file, line estimate, problem, fix.
Apply all fixes. List what changed.
```

---

## PHASE 3 — BUILD: CHAT INTERFACE + APP SHELL

### PROMPT B8 — Chat Interface

```
Build ChatInterface in frontend/src/components/ChatInterface.tsx for [PROJECT_NAME].

Props: none (uses useCart() context)

Local state:
- messages: Message[] (restore from sessionStorage on mount)
- input: string
- isLoading: boolean
- abortController: AbortController | null (for cancelling in-flight requests)

SEND MESSAGE:
1. Validate input is not empty and not loading
2. Create user message, append, clear input, set isLoading=true, scroll to bottom
3. Create placeholder assistant message {id, role:"assistant", content:"", isStreaming:true, timestamp:Date.now()}
4. Create AbortController, set state
5. for await (const event of streamChat(messages, sessionId)):
   - "text": update placeholder content (append), set isLoading=false
   - "parts": update placeholder parts array
   - "tool_call": update placeholder toolCall field
   - "cart_sync": dispatch SET_CART(event.content)
   - "done": set isStreaming=false, set responseTimeMs
   - "error": set error field, set isStreaming=false
6. Save messages to sessionStorage
7. In finally: set isLoading=false, set abortController=null

RETRY: "Try again" button in error MessageBubble calls handleSend with the same last user message content

LAYOUT (h-screen flex flex-col):
Header: logo left (brand icon + project name) | cart icon with badge count + trash icon right
  Cart icon click: opens CartSidebar
  Trash click: clear messages from state + sessionStorage

Messages area: flex-1 overflow-y-auto px-4 py-6
  Empty: WelcomeScreen (passes onSelect=handleSelect, filter, onFilterChange)
  Non-empty: MessageBubble per message, ref on last bubble, useEffect scroll-to-bottom

Input area: border-t bg-white px-4 py-3
  Textarea: auto-resize (1-4 rows), onKeyDown Enter without Shift → submit
  Submit button: [BRAND_COLOR] bg, disabled when empty or isLoading, spinner when isLoading
  Footer text: "Specialised in [SCOPE] · Always verify at [DATA_SOURCE]"

handleSelect(query): sets input = query, immediately calls handleSend
```

---

### PROMPT B9 — App Layout and Page

```
Build the Next.js app shell for [PROJECT_NAME].

frontend/src/app/layout.tsx:
metadata: title "[PROJECT_NAME]", description "AI assistant for [SCOPE]"
Wrap children in CartProvider
No other providers, no global nav

frontend/src/app/globals.css:
@tailwind base; @tailwind components; @tailwind utilities;
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.animate-fade-in { animation: fadeIn 0.3s ease-out; }
Custom scrollbar: thin width, gray-200 track, gray-400 thumb

frontend/tailwind.config.ts:
extend colors: brand-[PROJECT_NAME]: "[BRAND_COLOR]"
content: ["./src/**/*.{ts,tsx}"]

frontend/src/app/page.tsx:
"use client"
state: cartOpen (bool), filter (ApplianceFilter), filter passed down to ChatInterface via prop or context
Render: ChatInterface + CartSidebar(isOpen=cartOpen, onClose)
CartSidebar opened by header cart icon click in ChatInterface (use a callback prop or shared context)

frontend/next.config.ts:
images.remotePatterns: allow web.archive.org and [DATA_SOURCE domain]

Run npm run build and confirm zero TypeScript errors before continuing.
```

---

## PHASE 4 — AUDIT: FULL SYSTEM REVIEW

### AUDIT A3 — Senior PM Acceptance Criteria Check (PARALLEL with A4)

```
Act as a senior product manager reviewing [PROJECT_NAME] against REQUIREMENTS.md.

For each acceptance criterion in REQUIREMENTS.md, test it:
1. Read the criterion
2. Identify which file(s) implement it
3. Determine: PASS (clearly implemented), FAIL (not implemented or broken), PARTIAL (partially done)
4. For FAIL or PARTIAL: write the exact code change needed

Also audit:
- Are all 3 user personas served? For each persona, trace a realistic user journey through the code.
- Are all Must Have user stories implemented? Read the story, find the implementation.
- Does the scope boundary work? Find the exact code that enforces "only answer [SCOPE] questions."
- Is the decline message exactly as specified in REQUIREMENTS.md?
- Are the success metrics instrumentable? Is there any logging or tracking for each metric?

Write a report: criteria status table, unmet stories list, gaps between spec and implementation.
Fix all FAIL items. Note PARTIAL items for future work.
```

---

### AUDIT A4 — Senior Engineer System Audit (PARALLEL with A3)

```
Act as a principal engineer performing a final system audit of [PROJECT_NAME].

Read every file in the project. Report on:

ARCHITECTURE COMPLIANCE:
- Does the implementation match ARCHITECTURE.md decisions?
- Is the tool-use loop actually a loop (not a single call)?
- Are tools genuinely thin (no business logic, just data access)?
- Does Claude compose tools across multiple turns for complex queries?
- Is there any LangChain import anywhere? If yes, remove it.

DATA INTEGRITY:
- Are all 6 data files present in backend/app/data/ with non-zero sizes?
- Does the FAISS index have the same number of vectors as parts_metadata.json entries?
- Does symptom_map only contain normalized keys (no uppercase, no trailing punctuation)?
- Do all part IDs in symptom_map/type_map/model_map/brand_map exist in parts_metadata?

API CONTRACT:
- Does POST /chat return Content-Type: text/event-stream?
- Does every SSE event follow the format "data: {json}\n\n"?
- Does the stream always end with a "done" event?
- Does GET /health return 200 (not 500) even before any data is loaded?

DEAD CODE:
- List every function defined in backend/app/ that is never called
- List every import in frontend/src/ that is unused
- List any file in the project that is never imported or referenced

ENVIRONMENT VARIABLE SAFETY:
- Is ANTHROPIC_API_KEY never logged, never returned in API responses?
- Is .env in .gitignore? Is .env.example committed but .env not committed?
- Are there any hardcoded localhost URLs in the frontend? (should use NEXT_PUBLIC_BACKEND_URL)

Apply all fixes. Commit with message "audit: senior engineer system review".
```

---

## PHASE 5 — BUILD: DOCUMENTATION + DEPLOYMENT

### PROMPT B10 — All README Files (PARALLEL with B11)

```
Write four README files for [PROJECT_NAME].

ROOT README.md:
1. Live demo badge: **Live:** https://[URL]
2. One-paragraph description: conversational AI agent, Claude tool-use, FAISS, [DATA_SOURCE] data
3. Features: what the user can do (6 bullets)
4. Architecture ASCII diagram: every component, every connection labeled with protocol
5. Tech stack table: Layer | Technology | Why (reference ARCHITECTURE.md decisions)
6. Data coverage: entities indexed, models mapped, categories, brands — real numbers from the data
7. Quick start: exact commands with copy-paste blocks
8. Environment variables: table with name, required, default, description
9. Project structure tree (2 levels deep)
10. Known limitations: 3 real limitations with honest explanations
11. What's next: 3 extensions with effort estimate (Low/Medium/High)

backend/README.md:
1. Setup and env vars table
2. API routes: Method | Path | Description | Auth
3. Eight tools reference: Name | Triggers when | Data source | Typical latency
4. Data files loaded at startup: name, size, what it contains
5. Session lifecycle: creation, cart TTL, cleanup
6. Rate limiting: window, limit, per-IP logic

frontend/README.md:
1. Setup and env vars
2. Component hierarchy diagram (ASCII)
3. SSE event types table: type | content shape | what the frontend does
4. Cart persistence: localStorage keys, what is stored, when it is cleared
5. Design system: colors (only gray-* and brand color in product UI), no external UI library

scraper/README.md:
1. Pipeline steps with exact commands in order
2. Scraping approach explanation: why [APPROACH] was chosen over alternatives
3. Output files table: filename | size | contents | what reads it
4. Data coverage numbers
5. Runtime estimate and any API keys needed
```

---

### PROMPT B11 — Deployment Config (PARALLEL with B10)

```
Set up complete deployment for [PROJECT_NAME].

FILE: backend/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"

FILE: backend/.dockerignore
__pycache__
*.pyc
.env
*.db
.git

FILE: railway.toml (at REPO ROOT — not inside backend/ — Railway reads this from root only)
[build]
builder = "DOCKERFILE"
dockerfilePath = "backend/Dockerfile"
watchPatterns = ["backend/**"]
[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

FILE: backend/.env.example
ANTHROPIC_API_KEY=
ALLOWED_ORIGINS=http://localhost:3000

FILE: frontend/.env.local.example
NEXT_PUBLIC_BACKEND_URL=http://localhost:8001

DEPLOYMENT CHECKLIST (write into README.md under "Deploy"):

Railway (backend):
1. Push repo to GitHub: git push origin main
2. railway.app → New Project → Deploy from GitHub → select repo
3. Service Settings: Root Directory = backend
4. Variables: ANTHROPIC_API_KEY=[key], ALLOWED_ORIGINS=[vercel-url-no-trailing-slash]
5. Settings → Networking → Generate Domain → port 8080
6. Watch Deploy Logs for "Application startup complete"
7. Visit [railway-url]/health → should return {"status":"ok"}

Vercel (frontend):
1. vercel.com → New Project → import repo
2. Root Directory = frontend
3. Environment Variables: NEXT_PUBLIC_BACKEND_URL=[railway-url] ← NO trailing slash
4. Set for All Environments (Production + Preview + Development)
5. Deploy → visit [vercel-url] → UI should load

CORS fix (do this last):
Update Railway ALLOWED_ORIGINS = [vercel-url] (no trailing slash), Railway auto-redeploys.

COMMON ERRORS:
- "Failed to fetch": ALLOWED_ORIGINS wrong or has trailing slash
- POST //chat 404: NEXT_PUBLIC_BACKEND_URL has trailing slash — fix and redeploy Vercel
- OPTIONS /chat 400: Origin header doesn't exactly match ALLOWED_ORIGINS
- Build fails in 3s: railway.toml not at repo root
- "Application failed to respond": check Deploy Logs for startup crash — likely missing ANTHROPIC_API_KEY
```

---

### PROMPT B12 — Presentation Document

```
Write PRESENTATION.md for [PROJECT_NAME] — a 10-slide deck outline with full speaker notes.

For each slide: Headline, Visual description, Content (bullets or table), exact Speaker Notes (word-for-word what to say).

Slide 1 — The Problem (2 min)
Slide 2 — The Solution (2 min): show a table of input types → what happens
Slide 3 — Live Demo (15 min): narrate every click, read the talking point aloud, explain the risk alert
Slide 4 — Architecture (5 min): ASCII diagram, one sentence per component, explain every design choice
Slide 5 — How Claude Decides (5 min): explain tool-use API, no intent classifier, show compose example
Slide 6 — Data Pipeline (5 min): scraping approach + why, maps + FAISS, incremental refresh
Slide 7 — Streaming (3 min): SSE event types, why streaming matters for UX
Slide 8 — Evaluation (5 min): accuracy metrics, scope adherence, response time numbers
Slide 9 — Scalability (3 min): what breaks at 10x, migration path to Postgres, adding categories
Slide 10 — Q&A Prep: 8 questions with verbatim answers

Q&A questions must include:
1. Why Claude over GPT-4?
2. Why FAISS over a hosted vector DB?
3. How do you know the parts data is accurate?
4. What happens if [DATA_SOURCE] changes their site structure?
5. How would you add a new appliance category?
6. Why not LangChain?
7. How does this scale to 10 million parts?
8. What would you build next with two more weeks?

Also write a concise SCRIPT.md — one dense paragraph summarizing the entire technical architecture as a senior engineer would describe it to a client. Cover: agent loop, tool selection mechanism, retrieval tiers, data sourcing, streaming, deployment.
```

---

## PHASE 6 — FINAL AUDIT

### AUDIT A5 — Pre-Ship Checklist

```
Act as a tech lead doing a final pre-ship review of [PROJECT_NAME].

Run through this checklist and report PASS / FAIL for each item:

GIT:
- [ ] git status is clean (no uncommitted changes)
- [ ] .env is in .gitignore and NOT committed
- [ ] .env.example IS committed with placeholder values only
- [ ] No API keys in any committed file

FUNCTIONALITY:
- [ ] Backend /health returns 200
- [ ] POST /chat with a symptom query streams a response with parts
- [ ] POST /chat with a model number returns compatible parts
- [ ] POST /chat with a part number returns part details
- [ ] POST /chat with an out-of-scope query returns the decline message (not an error)
- [ ] manage_cart add/remove/view/clear all work correctly
- [ ] Frontend loads at localhost:3000 with welcome screen
- [ ] Suggestion chips submit and get a response
- [ ] Add to cart from ProductCard updates cart badge
- [ ] Cart sidebar opens, shows items, shows subtotal

DEPLOYMENT:
- [ ] Railway Deploy Logs show no errors
- [ ] /health returns 200 on the Railway URL
- [ ] Vercel build completes with zero errors
- [ ] Live URL loads the welcome screen
- [ ] A query from the live URL gets a real response (not CORS error)
- [ ] NEXT_PUBLIC_BACKEND_URL has no trailing slash
- [ ] ALLOWED_ORIGINS matches Vercel URL exactly

DOCUMENTATION:
- [ ] README.md has the correct live URL
- [ ] REQUIREMENTS.md exists
- [ ] ARCHITECTURE.md exists
- [ ] DESIGN.md exists
- [ ] All 4 README files written

For every FAIL: write the exact fix. Apply it. Re-run the check.
Commit: git add -A && git commit -m "chore: pre-ship audit fixes" && git push origin main
```

---

## PARALLEL EXECUTION MAP — 4-Hour Timeline

```
TIME    PROMPT          SESSION     NOTE
0:00    P1 Requirements   1         PM planning — do not skip
0:10    P2 Architecture   1
0:20    P3 System design  1
0:35    B1 Scaffold       1
0:45    B2 Scraper        1         START FIRST — takes 30-45 min in background
0:50    B3 Maps           2         PARALLEL
        B4 Backend+Tools  3         PARALLEL
1:20    A1 Backend audit  2         Code review while scraper runs
        B5 FAISS index    3         Can write code before data is ready
1:40    B6 Types+API      2         PARALLEL
        B7 Components     3         PARALLEL
2:10    A2 Frontend audit 2         PARALLEL
        B8 ChatInterface  3         PARALLEL
2:40    B9 App shell      1
2:55    A3 PM audit       2         PARALLEL final reviews
        A4 Engineer audit 3         PARALLEL
3:20    B10 READMEs       2         PARALLEL
        B11 Deployment    3         PARALLEL
3:50    B12 Presentation  1
4:10    A5 Pre-ship       1
4:30    Done — record/present
```

---

## CUT LIST — If You Run Out of Time

Cut in this order. Never cut items marked KEEP.

| Item | Cut? | Why it is safe to cut |
|------|------|----------------------|
| image proxy endpoint | Yes | Images just won't load in deployment |
| CartSidebar animations | Yes | Cart still works |
| ToolCallIndicator labels | Yes | Generic "thinking..." is fine |
| model compatibility live scrape fallback | Yes | Map lookup still works |
| sessionStorage message persistence | Yes | Page refresh loses history |
| P3 DESIGN.md full document | Partial | Write just the diagram section |
| A2 frontend audit | Yes | Ship with known minor issues |
| **Agent loop** | **KEEP** | Core of the project |
| **FAISS search** | **KEEP** | Core retrieval |
| **SSE streaming** | **KEEP** | Core UX |
| **Scope decline message** | **KEEP** | Evaluated criterion |
| **REQUIREMENTS.md** | **KEEP** | PM deliverable |
| **ARCHITECTURE.md** | **KEEP** | Design choices deliverable |
| **Presentation deck** | **KEEP** | You are presenting live |
