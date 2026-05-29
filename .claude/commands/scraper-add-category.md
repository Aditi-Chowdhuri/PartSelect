Add a new appliance category to the scraper pipeline. The user will specify the category name (e.g. "washing-machine", "dryer", "oven").

Do the following:
1. Read scraper/build_from_sitemap.py and identify where appliance categories are defined. Add the new category.
2. Read scraper/scrape_parts.py and confirm the category filter includes the new type.
3. Read scraper/build_relational_index.py and confirm no hardcoded category filters exclude the new type.
4. Read backend/app/claude_client.py and update the SYSTEM_PROMPT to include the new appliance in the scope. Change "refrigerator and dishwasher" to include the new category.
5. Read frontend/src/components/WelcomeScreen.tsx and add 4 suggestion queries for the new category under QUERIES_BY_FILTER.
6. Add a new filter tab for the category in the FILTERS array in WelcomeScreen.tsx.

After making all changes, list every file modified and what changed. Do not run the scraper — just prepare the code. Commit the changes.
