Verify that the demo queries used in STANDUP.md actually return good results from the local data index.

For each of these queries, check the data directly:
1. "My GE refrigerator is leaking water from the bottom" → check symptom_part_map.json for "leaking" under refrigerator, report part count
2. "What parts are compatible with model 25344352401?" → check model_part_map.json, report part count and category
3. "Tell me about part PS8746671" → check parts_metadata.json, report name, price, rating, review_count
4. "My dishwasher is not draining" → check symptom_part_map.json for drain under dishwasher, report part count
5. "Show me Samsung refrigerator parts" → check brand_appliance_map.json for Samsung refrigerator, report count

Also check the backup queries:
- PS732699 → name, price, rating
- 66512413N412 → model exists and part count

Report a pass/fail for each query. If any query returns 0 results or the part doesn't exist, flag it and suggest a replacement.
