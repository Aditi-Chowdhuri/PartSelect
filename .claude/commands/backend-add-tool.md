Add a new tool to the agent. The user will describe what the tool should do.

Do the following:
1. Read backend/app/tools.py — understand existing tool patterns and data structures.
2. Implement the new tool function following the same async pattern as existing tools.
3. Read backend/app/claude_client.py — add the tool to TOOL_DEFINITIONS (name, description, input_schema) and add a dispatch case in execute_tool().
4. If the tool returns parts, add an elif block in the parts_to_emit section to normalise and emit the results.
5. Update the SYSTEM_PROMPT in claude_client.py to include a TOOL SELECTION GUIDE entry for the new tool.

After implementing, show the complete diff. Do not run the server — just prepare the code. Commit the changes.
