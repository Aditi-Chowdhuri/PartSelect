# PartSelect Scraper & Data Pipeline

Builds the local FAISS vector index and relational maps used by the backend agent. No external API keys are required — everything runs locally.

---

## What it produces

| Output file | Destination | Contents |
|-------------|-------------|----------|
| `parts_raw.jsonl` | `scraper/data/` | 6,025 scraped part records |
| `faiss_index.bin` | `backend/app/data/` | 384-dim FAISS IndexFlatIP |
| `parts_metadata.json` | `backend/app/data/` | Part records for the index |
| `model_part_map.json` | `backend/app/data/` | 10,325 appliance models → compatible PS numbers |
| `symptom_part_map.json` | `backend/app/data/` | 72 "category\|symptom" keys → [PS numbers] |
| `part_type_map.json` | `backend/app/data/` | 87 "category\|type" keys → {parts, brands} |
| `brand_appliance_map.json` | `backend/app/data/` | 77 "Brand\|appliance" keys → {parts} |

---

## Setup

```bash
cd scraper
pip install -r requirements.txt
```

No `.env` file needed — the scraper uses only local models and writes to local disk.

---

## Pipeline steps

Run these in order. Each step's output feeds the next.

### Step 1 — Parse XML sitemaps

```bash
python build_from_sitemap.py
```

Reads the PartSelect XML sitemaps in `xml/` and fetches PTL (part-type landing) pages via Wayback Machine to classify each URL. Outputs:
- `scraper/data/sitemap_parts.json` — 15,857 classified part URLs
- `scraper/data/sitemap_models.json` — 287,259 appliance model URLs

The `xml/` directory is not committed (too large). Re-download the sitemaps from PartSelect if needed.

### Step 2 — Scrape parts

```bash
python scrape_parts.py
```

For each part URL: tries the live PartSelect page first, falls back to the Wayback Machine archive. Parses name, price, brand, description, rating, review count, symptoms, compatible models, install difficulty, install time, and video URL.

- **Concurrency:** 5 workers, 1–2 s delay per request
- **Runtime:** ~3 hours for 6,025 parts
- **Output:** `scraper/data/parts_raw.jsonl`

### Step 3 — Build relational maps

```bash
python build_relational_index.py
```

Reads `parts_raw.jsonl` and builds all four relational JSON maps in `scraper/data/`. These maps enable fast structured lookups (by model number, symptom, part type, and brand) before falling back to FAISS.

### Step 4 — Embed and index

```bash
python embed_and_index.py
```

Loads `parts_raw.jsonl`, encodes each part with `all-MiniLM-L6-v2` (sentence-transformers, 384 dimensions), and builds a FAISS `IndexFlatIP` with L2-normalised vectors (cosine similarity). Copies the index binary and all relational maps to `backend/app/data/`.

After this step, restart the backend to pick up the new data.

---

## Data coverage

| Metric | Count |
|--------|-------|
| Parts indexed | 6,025 |
| Refrigerator parts | 4,866 (80.8%) |
| Dishwasher parts | 1,159 (19.2%) |
| Appliance models | 10,325 |
| Symptom mappings | 72 |
| Part type mappings | 87 |
| Brand × appliance keys | 77 |

---

## Notes

- PartSelect's CDN (Akamai) blocks direct scraping. The scraper uses the **Wayback Machine CDX API** as the primary data source for archived part pages from 2022–2024.
- `scraper/data/` is gitignored (large intermediate files). The final outputs in `backend/app/data/` are committed except for `faiss_index.bin` (binary, regenerate with `embed_and_index.py`).
- To add a new appliance category (e.g. washing machines): add the category to `scrape_parts.py`'s scope filter, re-run the pipeline, and update the scope guard in `backend/app/claude_client.py`'s system prompt. No other agent code changes are needed.
