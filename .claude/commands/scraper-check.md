Audit the current state of the scraped data. Check the following:

1. Read backend/app/data/parts_metadata.json — report total parts, breakdown by category (refrigerator vs dishwasher), brands present, average rating, how many have prices, how many have symptoms.
2. Read backend/app/data/model_part_map.json — report total models, breakdown by category.
3. Read backend/app/data/symptom_part_map.json — report total symptom keys, top 10 symptoms by part count.
4. Read backend/app/data/brand_appliance_map.json — list all brand+appliance combinations.
5. Check if backend/app/data/faiss_index.bin exists and report its file size.

Print a clean summary table of all coverage statistics. Flag anything that looks like missing data or anomalies.
