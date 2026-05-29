Run the full data scraping and indexing pipeline for this project. Execute the following steps in order from the scraper/ directory:

1. python build_from_sitemap.py — classify part URLs by appliance type from PartSelect XML sitemaps
2. python scrape_parts.py — fetch archived HTML snapshots from the Wayback Machine CDX API (takes ~3 hours, 5 workers)
3. python build_relational_index.py — build symptom_part_map.json, part_type_map.json, model_part_map.json from scraped data
4. python embed_and_index.py — embed part names/descriptions with all-MiniLM-L6-v2, build FAISS index, copy output files to backend/app/data/

After each step, report how many parts/models/symptoms were processed. If a step fails, show the error and stop. At the end confirm that backend/app/data/ contains: faiss_index.bin, parts_metadata.json, model_part_map.json, symptom_part_map.json, part_type_map.json, brand_appliance_map.json.
