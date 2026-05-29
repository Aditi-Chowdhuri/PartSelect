Start the backend server locally. From the backend/ directory:

1. Check that .env exists and contains ANTHROPIC_API_KEY. If missing, warn the user.
2. Check that app/data/ contains all 6 required files: faiss_index.bin, parts_metadata.json, model_part_map.json, symptom_part_map.json, part_type_map.json, brand_appliance_map.json. If any are missing, stop and tell the user to run /scraper-run first.
3. Run: python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
4. Confirm the server starts and GET /health returns 200 OK.
