# PartSelect Scraper & Data Pipeline

Scrapes refrigerator and dishwasher part data from PartSelect.com and indexes it into Pinecone for semantic search.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in PINECONE_API_KEY, OPENAI_API_KEY in .env
```

## Usage

```bash
# Step 1: Scrape (~10-15 min for 500 parts)
python scrape_parts.py

# Step 2: Embed and index (~5 min)
python embed_and_index.py

# Step 3: Verify
python search_test.py
```

## Output

- `data/parts_raw.json` — raw scraped parts (part number, name, price, brand, category, compatible models, image URL)
- Pinecone index `partselect-parts` — 1536-dim embeddings with metadata
