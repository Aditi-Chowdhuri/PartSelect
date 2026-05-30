# Conversational AI Agent — Build Playbook
# Based on: PartSelect Chat Agent

All prompts used to build this project from scratch, in order.
Copy-paste each one directly. Replace [BRACKETED] values before pasting.
Parallel steps are marked — open a second Claude session and run both simultaneously.

---

## BEFORE YOU START

Confirm you have:
- Python 3.11+
- Node.js 18+
- An Anthropic API key
- The data source URL and a strategy for scraping it (see scraping section)

Fill in your variables:
- [PROJECT_NAME] — e.g. partselect-agent
- [DOMAIN] — e.g. refrigerator and dishwasher parts
- [DATA_SOURCE] — e.g. PartSelect.com
- [ENTITY] — e.g. part, product, listing
- [SCOPE] — e.g. refrigerators and dishwashers

---

## PROMPT 1 — Project Scaffold

```
Create a full project scaffold for [PROJECT_NAME], a Claude-powered conversational AI agent for [DOMAIN].

Stack:
- Backend: FastAPI (Python 3.11), async, SSE streaming
- AI: Anthropic claude-sonnet-4-6 via the Anthropic Python SDK, tool-use loop
- Frontend: Next.js 14 App Router, TypeScript, Tailwind CSS
- Search: FAISS vector index with sentence-transformers
- Scraper: Python with httpx, asyncio, BeautifulSoup4

Directory structure — create all files as empty stubs:

[PROJECT_NAME]/
  backend/
    app/
      __init__.py
      main.py
      models.py
      tools.py
      claude_client.py
    data/              (empty — populated by scraper)
    requirements.txt
    .env
    .env.example
    Dockerfile
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
  README.md

After creating the structure:
1. cd frontend && npx create-next-app@latest . --typescript --tailwind --app --yes
2. cd backend && pip install fastapi uvicorn anthropic sentence-transformers faiss-cpu httpx beautifulsoup4 python-dotenv numpy pydantic
3. Write backend/requirements.txt with all packages pinned

Confirm every file exists.
```

---

## PROMPT 2 — Scraper: Capture the Data

```
Build the data scraper in scraper/scrape_data.py for [PROJECT_NAME].

SCRAPING STRATEGY FOR [DATA_SOURCE]:

[DATA_SOURCE] blocks direct CDN access. Use the Wayback Machine CDX API as the data source.

The CDX API works as follows:
- URL: http://web.archive.org/cdx/search/cdx
- Params: url=[domain]/[path]*, output=json, fl=original,timestamp,statuscode, filter=statuscode:200, collapse=urlkey, limit=50000
- This returns a list of all archived URLs matching the pattern
- To fetch a page: http://web.archive.org/web/[timestamp]/[original_url]

Build the scraper in three phases:

Phase 1 — discover_urls():
  Call the CDX API with the pattern for [ENTITY] pages on [DATA_SOURCE]
  Parse the response to extract original URLs and timestamps (use most recent snapshot)
  Save URL list to scraper/data/urls.json
  Print total URLs found

Phase 2 — scrape_page(url, timestamp):
  Fetch the archived snapshot via httpx
  Parse HTML with BeautifulSoup
  Extract these fields: [LIST YOUR FIELDS — e.g. name, part_number, price, brand, category, symptoms, compatible_models, rating, review_count, image_url, description, install_difficulty]
  Return a dict or None if the page cannot be parsed

Phase 3 — run():
  Load urls.json
  Use asyncio with semaphore(5) for concurrent fetching
  Retry failed fetches up to 3 times with 2s backoff
  Save all scraped records to scraper/data/parts_raw.json as a JSON array
  Print progress with tqdm
  Print final count: X scraped, Y failed

Run as: python scrape_data.py
```

---

## PROMPT 3 — Build Relational Maps

```
Build the relational index builder in scraper/build_index.py for [PROJECT_NAME].

Input: scraper/data/parts_raw.json (array of scraped [ENTITY] records)

Build these lookup maps and save each as a JSON file in scraper/data/:

1. [entity]_by_id.json — dict mapping each unique entity ID to the full record

2. symptom_[entity]_map.json — dict mapping normalized symptom strings to lists of entity IDs
   Normalize symptoms: lowercase, strip punctuation, collapse whitespace
   Key format: "[category]|[symptom]" e.g. "refrigerator|ice maker not making ice"
   Only include symptoms with at least 1 character after normalization

3. [entity]_type_map.json — dict mapping part type categories to lists of entity IDs
   Use keyword matching on the entity name to classify into categories
   Categories: [LIST YOUR CATEGORIES — e.g. "ice makers", "water filters", "door gaskets", "drain pumps"]
   For each category, also track which brands have entities in that category

4. model_[entity]_map.json — dict mapping appliance model numbers to lists of compatible entity IDs
   For each model, also store the category (e.g. refrigerator / dishwasher)
   Source: each entity record's compatible_models array

5. brand_appliance_map.json — dict mapping "[brand]|[category]" to lists of entity IDs
   e.g. "GE|refrigerator", "Bosch|dishwasher"

After building all maps, print a summary:
- Total entities
- Symptom map: X keys, Y total refs
- Type map: X keys
- Model map: X models
- Brand map: X brand+category combinations

Save all files to scraper/data/. Do not modify parts_raw.json.
```

---

## PROMPT 4 — FAISS Vector Index

```
Build the FAISS vector indexer in scraper/embed_and_index.py for [PROJECT_NAME].

Input: scraper/data/parts_raw.json

Steps:

1. Load all records from parts_raw.json
2. For each record, build an embedding text string combining the most descriptive fields:
   "[name] [category] [brand] [description] [symptoms joined with space]"
   Keep it under 512 tokens per record
3. Load sentence-transformers model: all-MiniLM-L6-v2
   This model outputs 384-dimensional vectors, runs on CPU, no GPU needed
4. Embed all records in batches of 64 using model.encode(batch, show_progress_bar=True)
5. Normalize vectors for cosine similarity: vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
6. Build FAISS IndexFlatIP (inner product = cosine similarity on normalized vectors)
7. Add all vectors to the index
8. Save: faiss.write_index(index, "scraper/data/faiss_index.bin")
9. Save metadata: for each record save the fields the backend needs at query time
   (id, name, price, brand, category, image_url, url, rating, review_count, symptoms, install_difficulty)
   Save as scraper/data/parts_metadata.json in the same order as the FAISS index

After saving:
Copy these files to backend/app/data/:
  faiss_index.bin
  parts_metadata.json
  symptom_[entity]_map.json
  [entity]_type_map.json
  model_[entity]_map.json
  brand_appliance_map.json

Print: total vectors indexed, index size, output files written.

Run as: python embed_and_index.py
```

---

## PROMPT 5 — Backend Tools

```
Build the 8 tools in backend/app/tools.py for [PROJECT_NAME].

These tools are thin data accessors. Each one loads data from the JSON files in backend/app/data/ at module startup (not per request). All data loading happens once when the module is imported.

DATA LOADING at module level:
_DATA_DIR = Path(__file__).parent / "data"
Load at import time: faiss_index, parts_metadata (list of dicts), symptom_map, type_map, model_map, brand_map
Also load the sentence-transformers model (all-MiniLM-L6-v2) for semantic search

IMPLEMENT THESE 8 TOOLS:

1. search_catalog(query: str, category: str = None, brand: str = None) -> list
   Embed the query with the same model used during indexing
   Normalize the query vector
   Search FAISS index for top 10 results
   Filter by category and brand if provided
   Return list of matching [entity] metadata dicts

2. get_[entity]_details(part_number: str) -> dict
   First try: fetch the live page from [DATA_SOURCE] directly
   If that fails (CDN block, timeout): fetch from Wayback Machine archive
   Parse the HTML and return full details
   Include: name, price, description, symptoms, compatible_models, rating, review_count, install_difficulty, image_url, url

3. check_model_compatibility(model_number: str) -> dict
   Look up model_number in model_map
   If found: return {"model": model_number, "category": category, "compatible_parts": [list of full part dicts from metadata]}
   If not found: try a live scrape of [DATA_SOURCE]/models/[model_number]
   Return {"model": model_number, "compatible_parts": [], "error": "not found"} if both fail

4. find_parts_by_symptom(symptom: str, category: str = None) -> list
   Normalize the symptom string (lowercase, strip punctuation)
   Search symptom_map for keys containing the normalized symptom
   Combine all matching part IDs, deduplicate
   Return up to 15 matching part metadata dicts

5. find_parts_by_type(part_type: str, category: str = None, brand: str = None) -> list
   Normalize part_type
   Search type_map for matching keys
   Filter by category and brand if provided
   Return up to 15 matching part metadata dicts

6. find_parts_by_brand(brand: str, category: str = None) -> list
   Normalize brand name
   Look up in brand_map using "[brand]|[category]" key pattern
   Return up to 20 matching part metadata dicts

7. manage_cart(session_id: str, action: str, part_number: str = None, name: str = None, price: float = None) -> dict
   actions: "add", "remove", "view", "clear"
   Store cart in a module-level dict keyed by session_id: _carts: dict[str, list]
   add: append {part_number, name, price, quantity:1} or increment quantity if already in cart
   remove: remove item by part_number
   view: return current cart
   clear: empty the cart
   Always return {"items": [...], "total": float, "count": int}

8. get_order(order_id: str = None) -> dict
   Return a message explaining that live order lookup is not available
   Direct user to [DATA_SOURCE] order tracking page

Each tool must:
- Have a docstring explaining when Claude should call it
- Catch all exceptions and return {"error": str(e)} rather than raising
- Be importable and callable standalone for testing

Also write TOOL_DEFINITIONS list — the tool definitions array passed to the Anthropic API.
Each definition needs: name, description (when to use it), input_schema with all parameters typed.
```

---

## PROMPT 6 — Agent Loop and SSE Streaming

```
Build the Claude agent loop and SSE streaming in backend/app/claude_client.py for [PROJECT_NAME].

This file implements the core agentic loop using the Anthropic Python SDK.

SYSTEM PROMPT:
Write a system prompt that:
1. Defines the assistant's role: helpful agent for [DATA_SOURCE] specializing in [SCOPE]
2. Gives explicit tool selection guidance for each of the 8 tools (one line each — when to use it)
3. States rules: always use tools before answering product questions, never invent part numbers or prices, cite [DATA_SOURCE], be concise, no emojis
4. States scope boundary: only answer questions about [SCOPE]. For everything else, politely decline with a specific message.

AGENT LOOP — async generator function run_agent(messages: list, session_id: str):
This is an async generator that yields SSE-formatted strings.

Loop logic:
1. Build conversation from messages list
2. Call anthropic.AsyncAnthropic.messages.create with streaming=False (tool-use loop, not streaming tokens)
   Use: model, max_tokens=4096, system=SYSTEM_PROMPT, tools=TOOL_DEFINITIONS, messages=conversation
3. Parse response.content blocks — collect text blocks and tool_use blocks
4. If tool_use blocks exist:
   - For each tool: yield SSE event {"type": "tool_call", "content": tool_name}
   - Execute all tools (use asyncio.gather for parallel execution)
   - For tools that return parts/entities: yield SSE event {"type": "parts", "content": [list of normalized part dicts]}
   - For manage_cart: yield SSE event {"type": "cart_sync", "content": cart_items}
   - Append assistant message and tool results to conversation
   - Loop back to step 2
5. If no tool_use blocks (final response):
   - Stream the text in word-sized chunks: split on whitespace, yield each chunk as {"type": "text", "content": chunk}
   - Yield {"type": "done", "content": ""}
   - Return (end generator)

RETRY LOGIC — wrap the Anthropic API call:
- On 429 or 529: wait 1s, 3s, then raise (max 3 attempts)
- On other APIStatusError: yield error SSE and return

PART NORMALIZATION — _normalise_part(p: dict) -> dict:
Produce a consistent shape for the frontend:
part_number, name, price (float), brand, category, image_url, url, description (truncated 300 chars),
rating (float), review_count (int), availability, symptoms (first 5), install_difficulty, install_time, video_url

SSE FORMAT — _sse(payload: dict) -> str:
return f"data: {json.dumps(payload)}\n\n"

TEXT STREAMING — _stream_text(text: str):
Split on whitespace keeping delimiters, buffer to ~4 chars, yield each buffer as a chunk
(This gives word-boundary streaming instead of character-by-character)

SESSION CLEANUP — run a background task that clears carts older than 2 hours from _carts dict
```

---

## PROMPT 7 — FastAPI Main

```
Build the FastAPI backend entry point in backend/app/main.py for [PROJECT_NAME].

SETUP:
- FastAPI app with title "[PROJECT_NAME] API"
- Load .env file on startup
- CORSMiddleware: allow_origins from ALLOWED_ORIGINS env var (comma-split + strip), allow_methods=["*"], allow_headers=["*"], allow_credentials=True
- Rate limiter: sliding window, 20 requests per 60 seconds per IP
  Use X-Forwarded-For header to get real IP (Railway proxy passes this)
  Store request timestamps in a module-level dict: _rate_data: dict[str, deque]
  Return 429 with Retry-After header if limit exceeded

MODELS (in backend/app/models.py):
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None

class CartItem(BaseModel):
    part_number: str
    name: str
    price: float
    quantity: int = 1

ROUTES:

GET /health:
  Return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

POST /chat:
  Body: ChatRequest
  Generate a session_id if not provided (use uuid4)
  Return StreamingResponse(run_agent(messages, session_id), media_type="text/event-stream")
  Add headers: Cache-Control: no-cache, X-Accel-Buffering: no (disables nginx buffering)

GET /image-proxy:
  Query param: url (str)
  Proxy image requests through the Wayback Machine CDN to avoid CORS issues with archived images
  Only allow URLs from [DATA_SOURCE] domain
  Return the image bytes with the correct content-type header
  Cache responses for 1 hour

All endpoints: proper error handling, log request method + path + status + duration
```

---

## PROMPT 8 — Frontend Types and API Client

```
Build the TypeScript types and API client for [PROJECT_NAME] frontend.

frontend/src/lib/types.ts:

type ApplianceFilter = "all" | "[category1]" | "[category2]"

interface Part {
  part_number: string
  name: string
  price: number
  brand: string
  category: string
  image_url: string
  url: string
  description: string
  rating: number
  review_count: number
  availability: string
  symptoms: string[]
  install_difficulty: string
  install_time: string
  video_url: string
}

interface CartItem {
  part_number: string
  name: string
  price: number
  quantity: int
}

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  parts?: Part[]
  error?: string
  isStreaming?: boolean
  toolCall?: string
  timestamp: number
  responseTimeMs?: number
}

interface SSEEvent {
  type: "text" | "parts" | "cart_sync" | "tool_call" | "done" | "error"
  content: string | Part[] | CartItem[]
}

frontend/src/lib/api.ts:

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL (no trailing slash — this causes //chat 404)

async function* streamChat(messages: Message[], sessionId: string): AsyncGenerator<SSEEvent>
  POST to ${BACKEND_URL}/chat
  Body: { messages: [{role, content}], session_id }
  Read response as a ReadableStream
  Parse SSE lines: lines starting with "data: " → parse JSON → yield as SSEEvent
  Handle connection errors: yield {type: "error", content: error.message}
  Track timing: record start time, include responseTimeMs in done event

function getImageUrl(originalUrl: string): string
  Return ${BACKEND_URL}/image-proxy?url=${encodeURIComponent(originalUrl)}

frontend/src/lib/store.ts:
Implement cart state management using React Context + useReducer (no external library):
- State: { items: CartItem[], sessionId: string }
- Actions: SET_CART (replaces entire cart from SSE cart_sync), CLEAR_CART
- sessionId: generate once with crypto.randomUUID(), persist in localStorage
- Cart items: persist in localStorage, restore on mount
- Export: useCart() hook, CartProvider component
```

---

## PROMPT 9 — Frontend Components

```
Build the React components for [PROJECT_NAME] frontend.

frontend/src/components/WelcomeScreen.tsx:
Props: onSelect(query: string), filter: ApplianceFilter, onFilterChange(f: ApplianceFilter)

Layout: centered, max-w-xl, py-12
- Logo/icon at top (wrench SVG in brand-orange square)
- Heading: "[PROJECT_NAME] Assistant"
- Subtitle: "Find the right [entity], check compatibility, and get help for your [SCOPE]."
- Filter tabs: "All" | "[Category1]" | "[Category2]" — tab bar with underline active state
- Suggestion chips: 4 per filter, 2-column grid
  Each chip: label (bold) + query preview (small gray text, line-clamp-1)
  On click: call onSelect(query)
- Capabilities list: 5 items with icons (Search, CheckCircle, ShoppingCart, Wrench, Package)

QUERIES for each filter — use only verified queries that return real data:
[all]: [PASTE 4 QUERIES THAT WORK]
[category1]: [PASTE 4 QUERIES]
[category2]: [PASTE 4 QUERIES]

frontend/src/components/ToolCallIndicator.tsx:
Props: toolName: string
Render a small pill: spinner icon + human-readable label for the tool name
Map tool names to labels: search_catalog → "Searching catalog", get_[entity]_details → "Looking up part", etc.

frontend/src/components/ProductCard.tsx:
Props: part: Part, onAddToCart(part: Part): void
Layout: white card, border-gray-200, rounded-xl, overflow-hidden
- Image: use getImageUrl(), 160px height, object-cover, gray-100 background fallback
- Body: name (font-medium), part_number (small gray), price (bold brand-orange), brand + category tags
- Rating: star icons + review count if rating > 0
- Install difficulty badge if present
- "Add to cart" button: full width, brand-orange background
- "View part" link: small gray text linking to original URL

frontend/src/components/CartSidebar.tsx:
Props: isOpen: boolean, onClose(): void
Slide-in from right, backdrop overlay
Header: "Cart" + X button + item count badge
Items list: each item shows name, part_number, quantity, price
Remove button per item (calls cart action)
Footer: subtotal, "Checkout on [DATA_SOURCE]" button (links to [DATA_SOURCE] cart URL)
Cart persists in localStorage via CartProvider

frontend/src/components/MessageBubble.tsx:
Props: message: Message
User messages: right-aligned, gray-100 background, rounded-2xl
Assistant messages: left-aligned, white, with avatar icon
  - If isStreaming: show blinking cursor at end of content
  - If toolCall: show ToolCallIndicator instead of content
  - If parts array exists: render ProductCard grid below text (2 columns on desktop)
  - If error: red border, error icon, "Try again" button
  - Footer: response time in ms if present
```

---

## PROMPT 10 — Chat Interface

```
Build the main ChatInterface component in frontend/src/components/ChatInterface.tsx for [PROJECT_NAME].

Props: none (reads from CartProvider context)

State:
- messages: Message[] — conversation history
- input: string — current input value
- isLoading: boolean — waiting for first token
- sessionId: string — from useCart() context

On mount: load messages from sessionStorage (persist conversation within tab)

SEND MESSAGE flow:
1. Append user message to messages, clear input, set isLoading=true
2. Create a placeholder assistant message with isStreaming=true
3. Call streamChat(messages, sessionId)
4. For each SSEEvent yielded:
   - type "text": append content to placeholder message content, set isLoading=false
   - type "parts": set parts array on placeholder message
   - type "tool_call": set toolCall on placeholder message
   - type "cart_sync": dispatch SET_CART action
   - type "done": set isStreaming=false, record responseTimeMs
   - type "error": set error on placeholder message, set isStreaming=false
5. Save messages to sessionStorage

LAYOUT (full height, flex column):
- Header: [PROJECT_NAME] logo/name left, clear-history trash icon + cart icon with badge count right
- Messages area: flex-1, overflow-y-auto, scroll to bottom on new message
  Padding: px-4, max-w-2xl mx-auto
  Empty state: show WelcomeScreen
- Input area: sticky bottom, white background, border-t
  Textarea: auto-resize, max 4 rows, submit on Enter (Shift+Enter for newline)
  Send button: brand-orange, disabled when empty or loading
  Footer: small gray text — "[Specialized in [SCOPE]] · Always verify at [DATA_SOURCE]"

CLEAR HISTORY: trash icon in header clears messages from state and sessionStorage

Export default memo(ChatInterface)
```

---

## PROMPT 11 — App Layout and Page

```
Build the Next.js app shell for [PROJECT_NAME].

frontend/src/app/layout.tsx:
- metadata: title "[PROJECT_NAME]", description "AI assistant for [SCOPE]"
- Import globals.css
- Wrap children in CartProvider
- No other wrappers needed

frontend/src/app/globals.css:
- Tailwind base, components, utilities directives
- Add CSS variable for brand color: --brand-orange: #e8651a (or your brand color)
- Add @keyframes fade-in and animate-fade-in utility class for WelcomeScreen entrance
- Custom scrollbar styles (thin, gray)

frontend/tailwind.config.ts:
- Extend colors: brand-orange: "#e8651a" (or your brand color)
- Content paths include src/**

frontend/src/app/page.tsx:
Client component.
State: filter (ApplianceFilter), cartOpen (bool)
Renders:
- ChatInterface (full height, handles everything)
- CartSidebar (isOpen=cartOpen, onClose=setCartOpen(false))
The cart icon in ChatInterface header sets cartOpen=true

frontend/next.config.ts:
- Allow image domains: web.archive.org, [DATA_SOURCE domain]

Run: npm run dev and confirm the welcome screen loads at localhost:3000
```

---

## PROMPT 12 — README Files

```
Write four README files for [PROJECT_NAME].

ROOT README.md:
1. Live demo: [URL]
2. One-paragraph description: what it does, what powers it, what data it uses
3. Features list: what users can do (6 bullets)
4. Architecture diagram (ASCII): Browser → Next.js → FastAPI → Claude API + FAISS + Data Maps
5. Tech stack table: Layer | Technology | Why
6. Quick start: backend (copy .env, pip install, uvicorn), scraper (run pipeline), frontend (npm install, npm run dev)
7. Data coverage table: entities indexed, models mapped, category counts, top brands
8. Known limitations table: 3 limitations with explanations
9. Project structure tree

backend/README.md:
1. Setup and env vars table (name, required, description)
2. API routes table: method, path, description
3. Eight tools reference: tool name, what it does, when Claude calls it
4. Data files the backend loads at startup and their sizes
5. Session lifecycle: how sessions work, cart TTL
6. Rate limiting: window, limit, how IPs are identified

frontend/README.md:
1. Setup and env vars
2. Component table: name, props, what it does
3. SSE event types: type, content shape, what the frontend does with it
4. Cart persistence: how localStorage is used, what the session ID is for
5. Design decisions: color palette, no external UI library, why

scraper/README.md:
1. Pipeline steps in order with commands
2. Why Wayback Machine (or your data source approach) — one paragraph
3. Output files table: filename, size, what it contains
4. Coverage stats
5. No API keys required note (or list what's needed)
```

---

## PROMPT 13 — Fix Design and Data Issues

```
Audit [PROJECT_NAME] for correctness issues before finalizing.

Run these checks:

1. VERIFY SUGGESTION QUERIES — for each query in WelcomeScreen.tsx:
   Check that the query returns real data from the local index files.
   For symptom queries: check symptom_map for the keyword, report part count.
   For model number queries: check model_map for the exact model number, report part count.
   For part number queries: check parts_metadata.json for the part number, report name and price.
   Replace any query that returns 0 results with a verified working query.

2. DESIGN AUDIT — read all files in frontend/src/components/:
   Flag any color class that is not gray-*, not brand-orange, not white, not red/amber/green for status only.
   Specifically: remove any text-blue-* or text-brand-blue from product UI — only use gray-900 and brand-orange.
   Flag any emoji in component output.

3. UNUSED DEPENDENCIES — check package.json and requirements.txt:
   Remove any package that is imported nowhere in the codebase.
   Run npm ls for frontend, pip list for backend — flag anything suspicious.

4. DEAD CODE — scan backend/app/tools.py and backend/app/claude_client.py:
   Remove any function that is defined but never called.
   Remove any import that is unused.

5. VERIFY DATA FILES — confirm backend/app/data/ contains all required files with non-zero sizes.
   List each file and its size in KB.

Report every issue found. Fix all of them. Commit the fixes.
```

---

## PROMPT 14 — Deployment

```
Deploy [PROJECT_NAME] to Railway (backend) and Vercel (frontend).

STEP 1 — Prepare deployment config:

backend/Dockerfile:
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"

backend/.dockerignore:
__pycache__, *.pyc, .env, .git

railway.toml at REPO ROOT (not inside backend/ — Railway only reads this from root):
[build]
builder = "DOCKERFILE"
dockerfilePath = "backend/Dockerfile"
watchPatterns = ["backend/**"]
[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

frontend/.env.local.example:
NEXT_PUBLIC_BACKEND_URL=http://localhost:8001

backend/.env.example:
ANTHROPIC_API_KEY=
ALLOWED_ORIGINS=http://localhost:3000

STEP 2 — Push to GitHub:
git add -A && git commit -m "Ready for deployment" && git push origin main

STEP 3 — Deploy backend on Railway:
1. railway.app → New Project → Deploy from GitHub
2. Select repo. Set Root Directory = backend in service Settings
3. Variables: add ANTHROPIC_API_KEY and ALLOWED_ORIGINS=https://[vercel-url].vercel.app
4. Networking → Generate Domain → enter port 8080
5. Watch Deploy Logs — wait for "Application startup complete" and GET /health 200 OK

STEP 4 — Deploy frontend on Vercel:
1. vercel.com → New Project → Import repo
2. Root Directory = frontend
3. Environment Variables: NEXT_PUBLIC_BACKEND_URL = https://[railway-url] (NO trailing slash — trailing slash causes //chat 404)
4. Set variable for All Environments (Production + Preview)
5. Deploy

STEP 5 — Fix CORS:
Update ALLOWED_ORIGINS on Railway to the exact Vercel URL with no trailing slash.
Railway redeploys automatically.

COMMON ERRORS:
- "Failed to fetch" = ALLOWED_ORIGINS doesn't match browser origin. Check for trailing slash.
- OPTIONS /chat returns 400 = same CORS issue.
- POST //chat returns 404 = NEXT_PUBLIC_BACKEND_URL has trailing slash. Fix and redeploy Vercel.
- "Application failed to respond" = check Deploy Logs for startup crash. Usually ANTHROPIC_API_KEY missing.
- Build failed in 3 seconds = railway.toml not at repo root.

STEP 6 — Update README with live URLs and commit.
```

---

## PROMPT 15 — Presentation Script

```
Write SCRIPT.md for [PROJECT_NAME] as a client-facing presentation document.

Write a single dense paragraph (senior engineer technical summary) covering:
- The Claude tool-use agent loop architecture (no LangChain, Anthropic SDK directly, ~40-line loop)
- The 8 tools as thin data accessors and how Claude selects between them
- Two-tier retrieval: relational JSON maps (<1ms) for structured queries, FAISS (<50ms) for semantic search
- How the data was sourced (Wayback Machine CDX API or your scraping approach)
- SSE streaming from FastAPI to Next.js — every token, tool call, cart update as a typed event
- The deployment stack

Then write a 10-slide presentation outline with speaker notes:
Slide 1: The problem — what the user cannot do with keyword search
Slide 2: The solution — what they can do with the agent (table: input type → what happens)
Slide 3: Live demo cue — say "let me show you"
Slide 4: Architecture diagram — ASCII, each component labeled
Slide 5: How Claude decides which tool — explain tool-use API, no intent classifier
Slide 6: Data pipeline — scraping approach, relational maps, FAISS indexing
Slide 7: SSE streaming — why streaming matters, the event types, frontend reaction
Slide 8: Evaluation — tool selection accuracy, scope adherence, response time
Slide 9: What's next — 3 extensions ranked Low/Medium/High effort
Slide 10: Likely Q&A — 5 questions with verbatim answers

Commit SCRIPT.md.
```

---

## PARALLEL EXECUTION MAP — 4-Hour Build

```
TIME    ACTION                              SESSION
0:00    Prompt 1: Scaffold                  1
0:10    Prompt 2: Scraper                   1 (starts scraping — takes 30-45 min)
0:15    Prompt 3: Relational maps           2 (can write code while 2 runs)
0:25    Prompt 4: FAISS index               2
0:35    Prompt 5: Backend tools             2
        Prompt 6: Agent loop                3 (parallel with tools)
1:00    Prompt 7: FastAPI main              2
1:10    Prompt 8: Frontend types + API      2
        Prompt 9: Frontend components       3 (parallel)
1:40    Prompt 10: Chat interface           2
1:55    Prompt 11: App layout + page        2
2:10    Scraper should be done by now — run Prompt 4 (embed) if not already
2:20    Prompt 13: Design + data audit      1
2:40    Prompt 12: READMEs                  1
        Prompt 15: Script + presentation    3 (parallel with READMEs)
3:00    Prompt 14: Deployment               1
3:40    Test live URL                       You
4:00    Done
```

---

## VARIABLES REFERENCE

| Variable | PartSelect Example | Your Value |
|----------|-------------------|------------|
| [PROJECT_NAME] | partselect-agent | |
| [DOMAIN] | appliance parts | |
| [DATA_SOURCE] | PartSelect.com | |
| [ENTITY] | part | |
| [SCOPE] | refrigerators and dishwashers | |
| [CATEGORY1] | refrigerator | |
| [CATEGORY2] | dishwasher | |
| [BRAND COLOR] | #e8651a | |
| [CART URL] | partselect.com/shopping-cart/ | |
