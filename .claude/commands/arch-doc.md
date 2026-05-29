Write or update the system architecture documentation for this project. Read the following files first to ensure accuracy:

- backend/app/main.py
- backend/app/claude_client.py
- backend/app/tools.py
- frontend/src/lib/api.ts
- frontend/src/components/ChatInterface.tsx

Then produce a complete architecture document covering:
1. High-level system diagram (ASCII) showing Browser → FastAPI → Claude → Tools → Data
2. SSE streaming event types (tool_call, text, parts, cart_sync, done)
3. The 8 tools: name, purpose, data source, latency
4. Two-tier retrieval: relational JSON maps (O(1)) vs FAISS semantic search (<50ms) vs live scrape (1-8s)
5. Session lifecycle: how sessions are created, how cart state is stored, TTL
6. Rate limiting: requests per window, per-IP sliding window
7. Data files loaded at startup and their sizes
8. Key design decisions with rationale

Write this to HLD.md and commit.
