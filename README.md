# PartSelect Chat Agent

An AI-powered chat assistant for finding refrigerator and dishwasher parts on PartSelect.com. Built with a Claude claude-sonnet-4-6 agent loop, FAISS semantic search, and real scraped part data.

---

## Quick Start (local)

**Prerequisites:** Python 3.11+, Node.js 18+

### 1. Backend

```bash
cd backend
cp .env.example .env          # then add your ANTHROPIC_API_KEY
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 2. Frontend

```bash
cd frontend
cp .env.example .env.local    # NEXT_PUBLIC_BACKEND_URL=http://localhost:8001
npm install
npm run dev                   # opens http://localhost:3000
```

---

## Architecture

```
frontend (Next.js)
  └── SSE stream  ──►  backend (FastAPI)
                            └── Claude claude-sonnet-4-6 agent loop
                                    ├── search_catalog          (FAISS semantic search)
                                    ├── get_part_details        (live PartSelect scrape + Wayback fallback)
                                    ├── check_model_compatibility (live scrape)
                                    ├── find_parts_by_symptom   (relational symptom map)
                                    ├── find_parts_by_type      (relational part-type map)
                                    ├── find_parts_by_brand     (relational brand map)
                                    ├── manage_cart             (in-memory, session-scoped)
                                    └── get_order               (demo data — see limitations)
```

### Data pipeline

| File | Contents |
|------|----------|
| `backend/app/data/faiss_index.bin` | 6,025 part vectors (all-MiniLM-L6-v2) |
| `backend/app/data/parts_metadata.json` | Full part records |
| `backend/app/data/model_part_map.json` | 10,325 appliance models → compatible PS numbers |
| `backend/app/data/symptom_part_map.json` | 72 symptoms → relevant parts |
| `backend/app/data/part_type_map.json` | 87 part types → parts + brands |
| `backend/app/data/brand_appliance_map.json` | 77 brand × appliance keys |

To rebuild the data index after re-scraping:

```bash
cd scraper
python build_relational_index.py
python embed_and_index.py
# restart the backend
```

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API key |
| `ALLOWED_ORIGINS` | optional | Comma-separated CORS origins (default: localhost:3000,3001) |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | ✅ | Backend URL (default: http://localhost:8001) |

---

## Known limitations

- **Order lookup is demo-only.** `get_order` returns simulated order data. PartSelect does not expose a public order API.
- **Part images are proxied via Wayback Machine.** PartSelect's CDN blocks hotlinking; images load from archive.org and may occasionally 404.
- **Dishwasher coverage is ~19% of the catalog** (1,159 / 6,025 parts). The scraper targeted both appliance types but the PartSelect sitemap has proportionally more refrigerator parts.
- **Rating and install difficulty data is sparse** (~3% and ~1% of parts respectively). This data was not consistently published on the scraped pages.
- **In-memory cart and sessions.** Cart contents are stored in the backend process and are lost on restart. The frontend persists the cart in localStorage as a fallback.

---

## Scope

The agent is scoped exclusively to refrigerator and dishwasher parts and will decline all other questions.
