# PartSelect Chat Agent

An AI-powered chat assistant for finding refrigerator and dishwasher parts on PartSelect.com. Customers describe a symptom, provide a model number, or search by brand — the agent finds the right part, explains it, and adds it to cart.

Built on a Claude claude-sonnet-4-6 tool-use agent loop with a local FAISS vector index over 6,025 real scraped parts.

---

## Quick Start

**Prerequisites:** Python 3.11+, Node.js 18+

### 1. Backend

```bash
cd backend
cp .env.example .env          # add your ANTHROPIC_API_KEY
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 2. Frontend

```bash
cd frontend
cp .env.example .env.local    # NEXT_PUBLIC_BACKEND_URL=http://localhost:8001
npm install
npm run dev                   # http://localhost:3000
```

---

## Project structure

```
partselect-agent/
├── backend/                    FastAPI backend + agent loop
│   ├── app/
│   │   ├── main.py             API routes, rate limiting, image proxy
│   │   ├── claude_client.py    Claude agent loop + SSE streaming
│   │   ├── tools.py            8 tool implementations
│   │   ├── models.py           Pydantic request models
│   │   └── data/               FAISS index + relational JSON maps
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                   Next.js 14 App Router chat UI
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx        Root state, SSE handling, cart + parts buffer
│   │   │   └── layout.tsx      HTML shell, favicon
│   │   ├── components/
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── ProductCard.tsx
│   │   │   ├── CartSidebar.tsx
│   │   │   ├── WelcomeScreen.tsx
│   │   │   └── ErrorBoundary.tsx
│   │   └── lib/api.ts          streamChat() SSE client
│   └── .env.example
│
├── scraper/                    Data pipeline (run once to build the index)
│   ├── build_from_sitemap.py   Parse XML sitemaps → classified part URLs
│   ├── scrape_parts.py         Fetch part pages via Wayback → parts_raw.jsonl
│   ├── build_relational_index.py  Build symptom/type/brand/model maps
│   └── embed_and_index.py      Encode with all-MiniLM-L6-v2 → FAISS index
│
├── README.md                   This file
├── HLD.md                      High Level Design (architecture + component breakdown)
└── DESIGN.md                   Design decisions and rationale
```

---

## Architecture

```
frontend (Next.js)
  └── SSE stream  ──►  backend (FastAPI)
                            └── Claude claude-sonnet-4-6 agent loop
                                    ├── search_catalog          (FAISS semantic search)
                                    ├── get_part_details        (live scrape + Wayback fallback)
                                    ├── check_model_compatibility (live scrape)
                                    ├── find_parts_by_symptom   (relational symptom map)
                                    ├── find_parts_by_type      (relational part-type map)
                                    ├── find_parts_by_brand     (relational brand map)
                                    ├── manage_cart             (in-memory, session-scoped)
                                    └── get_order               (demo data — see limitations)
```

See [HLD.md](HLD.md) for the full component breakdown, request lifecycle, security model, and deployment instructions.

---

## Data index

| File | Contents |
|------|----------|
| `backend/app/data/faiss_index.bin` | 6,025 part vectors (all-MiniLM-L6-v2, 384-dim) |
| `backend/app/data/parts_metadata.json` | Full part records |
| `backend/app/data/model_part_map.json` | 10,325 appliance models → compatible PS numbers |
| `backend/app/data/symptom_part_map.json` | 72 symptoms → relevant parts |
| `backend/app/data/part_type_map.json` | 87 part types → parts + brands |
| `backend/app/data/brand_appliance_map.json` | 77 brand × appliance keys |

To rebuild after re-scraping:

```bash
cd scraper
python build_relational_index.py
python embed_and_index.py
# then restart the backend
```

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins (default: localhost:3000 and :3001) |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | Yes | Backend URL (default: http://localhost:8001) |

---

## Known limitations

| Limitation | Detail |
|------------|--------|
| Order lookup is demo-only | `get_order` returns simulated data. PartSelect has no public order API. |
| Part images via Wayback | PartSelect's CDN blocks hotlinking; images are proxied from archive.org and may 404. |
| Dishwasher coverage ~19% | 1,159 of 6,025 indexed parts. Mirrors the source sitemap distribution. |
| Rating data sparse | ~3% of parts have ratings. Not consistently published on source pages. |
| In-memory cart | Cart is lost on server restart. Frontend localStorage provides client-side persistence. |
| Prices not real-time | Scraped at index time (2022–2024 Wayback snapshots). |

---

## Scope

The agent handles refrigerator and dishwasher parts only. All other questions are declined.
