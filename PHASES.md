# PartSelect Agent — Phase Task Tracker

Update task status with: `[ ]` = pending, `[x]` = done, `[~]` = in progress, `[!]` = blocked

---

## Phase 1 — Hour 0–3: Core Functionality ✅ COMPLETE

### Backend
- [x] FastAPI app with `/chat` streaming endpoint
- [x] Claude tool-use loop (`claude_client.py`)
- [x] `search_catalog` tool (FAISS semantic search, 6,025 real parts)
- [x] `get_part_details` tool (live PartSelect scrape + Wayback fallback)
- [x] `check_model_compatibility` tool (live scrape, 10,325 models)
- [x] `manage_cart` tool (in-memory, session-scoped, SSE cart_sync to frontend)
- [x] `get_order` tool (demo data — documented as known limitation)
- [x] `find_parts_by_symptom` tool (72 symptoms mapped)
- [x] `find_parts_by_type` tool (87 part types mapped)
- [x] `find_parts_by_brand` tool (77 brand/appliance keys)
- [x] Scope guard in system prompt (refrigerator & dishwasher only)
- [x] Structured `parts` + `cart_sync` + `tool_call` SSE events

### Frontend
- [x] Streaming chat with typing indicator
- [x] Tool-call loading indicator
- [x] Welcome screen with example queries and filter tabs
- [x] Appliance filter (All / Refrigerator / Dishwasher)
- [x] Product cards inline in chat (no image, clean text layout)
- [x] Cart sidebar with running total, quantity controls, per-item links
- [x] Cart syncs when Claude adds/removes items via manage_cart
- [x] localStorage cart persistence across page reloads
- [x] Suggested follow-up chips
- [x] Markdown rendering (bold, lists, tables, inline code)
- [x] Parts buffered until text starts streaming (context before cards)

### Config & DX
- [x] `backend/.env.example` (ANTHROPIC_API_KEY + ALLOWED_ORIGINS)
- [x] `frontend/.env.example` (correct port 8001)
- [x] `.gitignore` (keys, binaries, raw scraper data)
- [x] `README.md` with setup instructions, architecture, known limitations

---

## Phase 2 — Hour 3–24: Data Pipeline & Polish ✅ COMPLETE

### Data
- [x] Scraper ran to completion — 6,025 unique parts (4,866 fridge / 1,159 dishwasher)
- [x] FAISS index built (all-MiniLM-L6-v2, IndexFlatIP, cosine similarity)
- [x] `model_part_map.json` — 10,325 appliance models
- [x] `symptom_part_map.json` — 72 symptoms
- [x] `part_type_map.json` — 87 part types
- [x] `brand_appliance_map.json` — 77 brand/appliance keys
- [x] Zero-price parts filtered from all search results
- [x] Generic video channel URLs stripped (only real watch?v= links surfaced)

### UI Polish
- [x] Claude.ai-inspired interface — clean text flow, no chat bubbles for assistant
- [x] Wrench favicon + consistent icon branding throughout
- [x] Single colour palette (gray scale + brand-orange CTA only)
- [x] Error boundary with retry button
- [x] Rate limiting (20 req/60s) + session TTL cleanup
- [x] CORS origin env-configurable (`ALLOWED_ORIGINS`)
- [x] Retry-After header on 429 responses

---

## Phase 3 — Hour 24–48: Deployment & Submission

### Deployment
- [ ] Frontend deployed to Vercel
- [ ] Backend containerised and deployed to Railway or Render
- [ ] `NEXT_PUBLIC_BACKEND_URL` env var set on Vercel
- [ ] `ALLOWED_ORIGINS` set to Vercel frontend URL on backend
- [ ] Live demo URL verified end-to-end

### Submission
- [ ] Slide deck / design writeup
- [ ] Demo video / walkthrough recorded
- [x] README with setup instructions
- [ ] Repo pushed and submission link sent
