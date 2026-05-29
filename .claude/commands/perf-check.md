Analyse the performance characteristics of the agent. Read backend/app/tools.py and backend/app/claude_client.py and report:

1. Data loading — which files are loaded at startup vs per-request. Estimate memory footprint (parts_metadata ~4.6MB, faiss_index ~8.8MB, maps ~2MB total).
2. Tool latencies — for each of the 8 tools, classify as: map lookup (O(1), <1ms), FAISS search (<50ms), or live HTTP scrape (1-8s).
3. Streaming — confirm the SSE parts buffer pattern: parts are held until first text token, then flushed atomically. Check if this is implemented correctly.
4. Rate limiting — confirm the sliding window parameters (20 req/60s per IP). Check if X-Forwarded-For is used for Railway's reverse proxy.
5. Retry logic — confirm _RETRY_DELAYS and _RETRY_STATUSES for Anthropic API 429/529 errors.
6. Session TTL — check how long cart sessions are kept in memory.

Report any performance bottlenecks or missing optimisations.
