Run an evaluation of the agent's tool selection accuracy. Do the following:

1. Read backend/app/tools.py to understand what each tool does and what inputs it expects.
2. Read backend/app/claude_client.py to see the TOOL SELECTION GUIDE in the system prompt.
3. Create a test set of 20 queries covering all tool types:
   - 3 symptom queries → should call find_parts_by_symptom
   - 3 model number queries → should call check_model_compatibility
   - 3 part number queries → should call get_part_details
   - 3 brand queries → should call find_parts_by_brand
   - 3 part type queries → should call find_parts_by_type
   - 2 general queries → should call search_catalog
   - 2 out-of-scope queries → should decline without tool call
   - 1 cart query → should call manage_cart

4. For each query, predict which tool Claude should select based on the system prompt.
5. Report the test set as a table: Query | Expected Tool | Reasoning.

Do not actually call the API — this is a static analysis of tool routing logic.
