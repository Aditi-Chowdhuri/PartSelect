Debug a backend issue. Read the following files and identify the problem:

1. backend/app/main.py — check route definitions, CORS setup, rate limiter, session manager
2. backend/app/claude_client.py — check the agent loop, tool executor, SSE helpers, retry logic
3. backend/app/tools.py — check data loading, FAISS index loading, all 8 tool implementations
4. backend/requirements.txt — check for missing or conflicting dependencies

Common issues to look for:
- ANTHROPIC_API_KEY not set (check os.getenv usage)
- Data files missing from backend/app/data/
- FAISS index shape mismatch with embedding model
- CORS origins not matching the frontend URL
- Port conflicts (default is 8001 locally, $PORT on Railway)
- Rate limiter blocking legitimate requests

Report the likely cause and the exact fix.
