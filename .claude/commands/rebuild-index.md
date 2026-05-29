Rebuild the FAISS vector index and relational maps from existing scraped data without re-scraping.

This assumes parts_raw.json already exists in scraper/data/. Do the following:

1. From scraper/ run: py -3 build_relational_index.py
   Report: symptom keys, part type keys, model keys produced.

2. From scraper/ run: py -3 embed_and_index.py
   Report: number of parts embedded, index size, files copied to backend/app/data/.

3. Confirm backend/app/data/ contains all 6 required files with non-zero sizes.

4. Restart the backend to reload the new index.

If any step fails, show the full error and stop.
