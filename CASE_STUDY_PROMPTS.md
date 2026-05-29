# Case Study Build Prompts — Copy-Paste Playbook

Generic prompt sequence for any AI-powered data pipeline + insights + dashboard case study.
Replace bracketed values before pasting. Parallel steps are marked — open a second Claude session and run both at the same time.
Designed for a 4-hour build + 1-hour live presentation.

---

## BEFORE YOU START — How to Scrape Any Website (Read This First)

Most people waste an hour trying BeautifulSoup on a JavaScript-rendered page and wonder why they get nothing. Follow this decision tree every time.

### Step A — Check if the data is in the HTML source (30 seconds)
Right-click the page → View Page Source (not Inspect — actual source). Press Ctrl+F and search for one piece of data you can see on screen (e.g. a contractor name, a price, a company name).

- **If you find it in the source**: BeautifulSoup works. Go to Step D.
- **If you do not find it**: The page is JavaScript-rendered. The data comes from an API call. Go to Step B.

### Step B — Find the API call in DevTools (2 minutes — do this first, always)
1. Open Chrome DevTools (F12) → Network tab
2. Click the **Fetch/XHR** filter button
3. **Hard refresh** the page (Ctrl+Shift+R) — this clears old requests
4. Interact with the page: run a search, click a filter, scroll to trigger load
5. Watch the Network tab — look for requests that return JSON (icon shows `{}`)
6. Click each one and check the **Preview** tab — find the one with your actual data
7. Right-click that request → **Copy → Copy as cURL (bash)**

What to capture:
- The full URL (including all query params)
- All request headers (especially: `Authorization`, `x-api-key`, `x-auth-token`, `Cookie`, `Referer`, `Origin`)
- The request body if it is a POST (click the **Payload** tab)
- The full JSON response (click **Preview** or **Response** tab, copy all)
- Look for pagination fields: `page`, `offset`, `skip`, `cursor`, `nextPageToken`, `total`, `hasMore`

**This API call is your scraper. You do not need BeautifulSoup at all.**

### Step C — If you find an API key in the headers (check this)
Sometimes the API key is a public token embedded in the page's JavaScript files.
- In DevTools → Sources tab → search (Ctrl+Shift+F) for the key value
- Or in Network tab → find a JS file → search for `apiKey`, `api_key`, `token`, `bearer`
- Public tokens like this are fine to use — they are not private credentials
- If the token expires (JWT with exp field): decode it at jwt.io to see the expiry. If it's short-lived, you need to automate the token refresh.

### Step D — If there is no API call visible (rare — use sitemap)
Some sites server-render everything with no separate API calls. Try the sitemap:
- Go to `https://[domain]/sitemap.xml` or `https://[domain]/sitemap_index.xml`
- If it exists, it lists all page URLs. Scrape the sitemap to get all entity URLs, then scrape each page with BeautifulSoup/httpx
- Look for the pattern: the sitemap often groups by type (e.g. `/contractors/sitemap.xml`, `/products/sitemap.xml`)

### Step E — Last resort: Playwright (only if A, B, D all failed)
Use Playwright only when the data requires JavaScript execution and there is no API and no sitemap.
- `pip install playwright && python -m playwright install chromium`
- Playwright can click, scroll, fill forms, and wait for network responses
- It is slow (1-2 seconds per page) — only use it if everything else fails

### What to paste into the scraper prompt (Prompt 3A)
You need exactly:
1. The cURL command (or URL + headers + body)
2. The raw JSON response for one full page of results (not just one record)
3. The name of the pagination field (e.g. "page 2 = add `?page=2` to the URL")
4. Whether auth headers expire and how to refresh them

---

## STEP 1 — Project Scaffold
*Run alone first. Takes 5 minutes.*

```
Create a full project scaffold for a [PROJECT_NAME] platform. The stack is:
- Backend: FastAPI (Python 3.11), SQLite for development, schema must be Postgres-compatible
- AI layer: Anthropic Claude claude-sonnet-4-6 via the Anthropic Python SDK
- Frontend: Next.js 14 App Router, TypeScript, Tailwind CSS
- Scraper: Python with httpx and asyncio

Create this exact directory structure with all files as empty stubs:

[PROJECT_NAME]/
  backend/
    app/
      main.py
      models.py
      database.py
      scraper.py
      insights.py
      evaluator.py
      routers/
        data.py
        insights.py
        export.py
    requirements.txt
    .env.example
    Dockerfile
    railway.toml
    .dockerignore
  frontend/
    src/
      app/
        page.tsx
        layout.tsx
        globals.css
      components/
        DataCard.tsx
        InsightPanel.tsx
        FilterBar.tsx
        PriorityBadge.tsx
        AlertBanner.tsx
        Dashboard.tsx
      lib/
        api.ts
        types.ts
    package.json
    tailwind.config.ts
    next.config.ts
    .env.local.example
  scraper/
    fetch_data.py
    build_insights.py
    evaluate_insights.py
    run_pipeline.py
  EVALUATION.md
  README.md

After creating the structure:
1. Run: cd [PROJECT_NAME]/frontend && npx create-next-app@latest . --typescript --tailwind --app --yes
2. Run: cd [PROJECT_NAME]/backend && pip install fastapi uvicorn sqlalchemy httpx anthropic python-dotenv tqdm alembic pydantic aiofiles
3. Write backend/requirements.txt with all installed packages pinned to current versions

Confirm every file and directory exists when done.
```

---

## STEP 2 — Database Schema
*Run after Step 1. Takes 5 minutes.*

```
Write the complete SQLAlchemy ORM database schema in backend/app/database.py for [PROJECT_NAME].

The main data entity is [ENTITY_NAME] (e.g. contractor, property, listing, company). For each record store:
- Raw data fields from the source: [LIST YOUR FIELDS — e.g. name, address, city, zip, phone, rating, review_count, tier, certifications, website, latitude, longitude]
- Metadata: source_id (unique, from the scraped source), raw_json (full original response as text), created_at, updated_at, data_quality_issues (JSON array of strings)

The insights table stores AI-generated intelligence per entity:
- entity_id (FK), generated_at, model_used, prompt_version
- business_summary (text), talking_point (text), risk_alert (text)
- priority ("High" / "Medium" / "Low"), priority_reasoning (text)
- next_action (text), next_action_type ("call" / "email" / "brochure" / "visit")
- insight_score (float 0-1), score_breakdown (JSON)
- flagged_for_review (bool default false), flag_reason (text nullable)

The evaluations table stores automated + human quality scores per insight:
- insight_id (FK), evaluated_at, evaluator ("auto" / "human")
- relevance_score, actionability_score, accuracy_score, clarity_score, overall_score (all float 0-1)
- notes (text)

The pipeline_runs table logs every scraper execution:
- run_at, territory (zip or equivalent), radius
- records_fetched, records_new, records_updated
- insights_generated, insights_flagged
- errors (JSON array), duration_seconds

Requirements:
- SQLAlchemy 2.0 declarative style
- get_db() FastAPI dependency
- init_db() that creates all tables on startup
- upsert_entity(session, data: dict) helper that inserts or updates on source_id conflict
- All types Postgres-compatible (no SQLite-only syntax)
- Write backend/app/models.py with matching Pydantic response schemas for all tables including paginated response wrapper
```

---

## STEP 3A + 3B — Run These Two in Parallel
*Open two Claude sessions. Paste 3A in one, 3B in the other. Start both at the same time.*
*3A runs 30-45 minutes. 3B takes 10 minutes. Move to Step 4 once 3B finishes — do not wait for 3A.*

---

### STEP 3A — Data Scraper (Start first — runs in background)

```
Build the async data scraper in scraper/fetch_data.py for [PROJECT_NAME].

SCRAPING APPROACH: [PICK ONE AND DELETE THE OTHERS]

--- IF YOU FOUND AN API CALL IN DEVTOOLS ---
Here is the real network request I captured from [DATA_SOURCE]:
CURL COMMAND: [PASTE FULL CURL HERE]
SAMPLE JSON RESPONSE: [PASTE FULL RAW JSON HERE]
Pagination field: [e.g. "page" — increment from 1, stop when results array is empty]
Total count field: [e.g. "total" — use this to calculate total pages]

Build the scraper using httpx.AsyncClient, replicating all headers from the cURL command exactly.

--- IF THE SITE HAS A SITEMAP ---
Sitemap URL: [PASTE URL e.g. https://domain.com/sitemap.xml]
Each page URL pattern looks like: [e.g. https://domain.com/contractors/[slug]]
The data fields I need from each page: [LIST FIELDS]

Build the scraper in two phases:
Phase 1 — parse the sitemap XML to extract all entity URLs (use httpx + xml.etree.ElementTree)
Phase 2 — fetch each URL with httpx, parse HTML with BeautifulSoup, extract the fields

--- IF USING BEAUTIFULSOUP DIRECTLY ---
The page URL pattern is: [e.g. https://domain.com/search?zip=10013&page=1]
The HTML elements containing the data: [describe the CSS selectors or HTML structure you observed]
Build the scraper using httpx + BeautifulSoup4.

--- REQUIREMENTS FOR ALL APPROACHES ---
1. Accepts --zip [VALUE] --radius [MILES] as CLI args (or equivalent territory param)
2. Handles all pages until exhausted
3. httpx.AsyncClient with semaphore(5) — max 5 concurrent requests
4. Retry failed requests up to 3 times: wait 2s, 6s, 18s between attempts
5. On 429 rate limit: wait 60 seconds then retry
6. Parse each record and call upsert_entity() — insert if new, update if source_id exists
7. For each record, detect and log data quality issues: missing phone, missing rating, no reviews, no address, no website
8. Skip records updated in last 24 hours unless --force flag is passed
9. tqdm progress bar showing current/total
10. Write a pipeline_runs record at end
11. Print final summary: X new, Y updated, Z skipped, W errors

Runnable as: python fetch_data.py --zip 10013 --radius 10 [--force]

Add a --audit flag that just prints data quality stats without scraping:
total records, % with each key field, breakdown by [MAIN_CATEGORY], top data quality issues
```

---

### STEP 3B — FastAPI Backend (Run in parallel with 3A)

```
Build the complete FastAPI backend in backend/app/main.py and the router files for [PROJECT_NAME].

backend/app/main.py:
- FastAPI app with title, version
- CORSMiddleware: allow_origins from ALLOWED_ORIGINS env var (comma-split), all methods, all headers, credentials=True
- Request timing middleware: log method + path + status + duration
- Include routers: data, insights, export
- GET /health → {"status": "ok", "record_count": int, "insight_count": int}
- Call init_db() on startup lifespan

backend/app/routers/data.py:
GET /[entities]:
  Filters: territory, priority, [FILTER_1 e.g. tier], [FILTER_2 e.g. min_rating], has_alert (bool), search (text on name+address), sort_by (priority/rating/name/created_at), page (int), page_size (int default 20)
  Returns: { items: [...with latest insight attached...], total: int, page: int, page_size: int }

GET /[entities]/{id}: full record + latest insight + all evaluations

backend/app/routers/insights.py:
POST /insights/{entity_id}/regenerate — trigger fresh insight generation
PATCH /insights/{insight_id}/flag — body: { reason: string }
GET /insights/flagged — all flagged insights with entity info attached

backend/app/routers/export.py:
GET /export/csv — same filters as list, returns CSV download
  Columns: name, [key fields], priority, talking_point, next_action, phone
GET /export/summary → { total, by_priority, by_[CATEGORY], avg_score, flagged_count }

All routes: typed Pydantic response_model, 404/422 error handling, async DB access.

backend/.env.example:
ANTHROPIC_API_KEY=
ALLOWED_ORIGINS=http://localhost:3000
DATABASE_URL=sqlite:///./[project].db
```

---

## STEP 4A + 4B — Run These Two in Parallel
*Start both as soon as Step 3B is done. Scraper (3A) is still running — that is fine.*

---

### STEP 4A — AI Insights Engine

```
Build the AI insights engine in scraper/build_insights.py for [PROJECT_NAME].

Use Anthropic Python SDK with Claude claude-sonnet-4-6. Generate all 5 insight fields in a single API call per record using tool_use for structured output. Enable prompt caching on the system prompt with cache_control type="ephemeral".

SYSTEM PROMPT:
You are a senior B2B sales strategist for [COMPANY/INDUSTRY]. You specialize in [DOMAIN]. Your job is to analyze [ENTITY_TYPE] records and generate pre-call sales intelligence for reps. You write concisely — reps read this in 30 seconds before a call. Never fabricate details not present in the input. If a field is missing, work with what you have.

USER PROMPT template:
Analyze this [ENTITY_NAME] and generate sales intelligence.
Name: {name}
[FIELD_1 — e.g. Tier]: {value}
[FIELD_2 — e.g. Rating]: {value} ({review_count} reviews)
[FIELD_3 — e.g. Certifications]: {value}
[FIELD_4 — e.g. Years in business]: {value}
Location: {city}, {zip}
Website: {website or "none"}

Tool schema (enforce this output exactly):
{
  "business_summary": "2-3 sentences on scale, activity level, market position",
  "talking_point": "one specific cold-call opening line using their actual data — not generic",
  "risk_alert": "one sentence red flag, or 'None identified'",
  "priority": "High | Medium | Low",
  "priority_reasoning": "one sentence explanation",
  "next_action": "specific recommended action with context",
  "next_action_type": "call | email | brochure | visit"
}

Pipeline:
- Query records with no insight OR insight older than 48h (skip fresh ones unless --force)
- Batches of 20, asyncio.gather with semaphore(5)
- Write each result to insights table immediately after generation
- Handle 429/529: wait 60s on 429, 30s on 529, retry up to 3 times
- Log token usage per batch, print running cost estimate ($3/1M input, $15/1M output for Sonnet)
- End summary: total generated, skipped, tokens used, estimated cost

Runnable as: python build_insights.py --zip 10013 [--force]
```

---

### STEP 4B — Frontend Types and Components

```
Build the complete frontend type system and component library for [PROJECT_NAME].

frontend/src/lib/types.ts:
- [EntityName]: all DB fields
- Insight: all insight fields
- Evaluation
- [EntityName]WithInsight: entity + latest insight field
- Priority = "High" | "Medium" | "Low"
- FilterState: { territory: string, priority: Priority[], [filter1]: string, [filter2]: number, hasAlert: boolean, sortBy: string, search: string, page: number }
- PaginatedResponse<T>: { items: T[], total: number, page: number, page_size: number }
- SummaryStats: { total: number, by_priority: Record<Priority,number>, avg_score: number, flagged: number }

frontend/src/lib/api.ts:
const BASE = process.env.NEXT_PUBLIC_BACKEND_URL (never add trailing slash)
- getEntities(filters): Promise<PaginatedResponse<[EntityName]WithInsight>>
- getEntity(id): Promise<[EntityName]WithInsight>
- searchEntities(q): Promise<[EntityName]WithInsight[]>
- regenerateInsight(entityId): Promise<Insight>
- flagInsight(insightId, reason): Promise<void>
- getFlagged(): Promise<[EntityName]WithInsight[]>
- getSummary(): Promise<SummaryStats>
- exportCSV(filters): void — builds URL params, triggers window.location

PriorityBadge.tsx: colored pill — High=red-600, Medium=amber-500, Low=gray-400. Compact, inline.

AlertBanner.tsx: renders nothing if alert is null or "None identified". Otherwise amber row with warning icon.

InsightPanel.tsx (fits in 420px right panel):
- Header: entity name + PriorityBadge
- Orange-tinted callout box labeled "Use this on the call": talking_point field
- business_summary as paragraph
- AlertBanner for risk_alert
- Next action row: icon based on next_action_type + next_action text
- Footer: insight_score thin progress bar, generated timestamp, Flag button (opens reason text input), Regenerate button with loading spinner

DataCard.tsx (compact, 6+ visible without scroll):
- name, [KEY_FIELD] badge, city, [rating or key metric], PriorityBadge
- One-line business_summary truncated with line-clamp-1
- Orange left border when selected=true

FilterBar.tsx (single row on desktop):
- Territory text input, Priority multi-checkbox, [FILTER_1] select, [FILTER_2] range/toggle, Alert toggle, Sort select, Search text input
- Every change fires onChange(newFilters) immediately — no submit button
```

---

## STEP 5 — Dashboard Pages
*Run after Step 4B is done.*

```
Build the main dashboard pages for [PROJECT_NAME].

frontend/src/app/page.tsx — Rep Dashboard:
Layout: FilterBar at top. Below: left 38% = scrollable DataCard list with "Showing X of Y" header. Right 62% = InsightPanel (shows empty state placeholder when nothing selected).

Behaviour:
- On mount: getEntities(defaultFilters), display results
- Card click: open InsightPanel on right, mark card selected
- Filter change: re-fetch, reset to page 1
- Load more button at bottom (or infinite scroll)
- Top-right: Export CSV button, stat chips: total count, High priority count (red), alert count (amber)
- Keyboard: arrow keys navigate cards, Escape deselects

frontend/src/app/manager/page.tsx — Manager Dashboard:
Top section — Flagged Insights (getFlagged() on mount):
- List: entity name, flag_reason, insight snippet, "Mark Reviewed" button
- Green banner if empty

Middle — Summary Stats (getSummary()):
- 4 stat cards: Total, High priority, Avg score, Flagged
- Priority bar chart using plain Tailwind divs (no library): three colored bars with labels and counts

Bottom — Table View:
- Sortable columns: name, [CATEGORY], rating, priority, insight_score, flagged
- Click row → modal with full InsightPanel
- Bulk checkboxes → Export CSV for selected
- Regenerate button per row

Top nav: "Rep View" | "Manager View" links.

Design: B2B professional.
- Primary text: gray-900
- Accent: blue-700
- High=red-600, Medium=amber-500, Low=gray-400
- Background: gray-50, cards: white with border-gray-200
- No custom fonts, no emojis
```

---

## STEP 6A + 6B — Run These Two in Parallel

---

### STEP 6A — Automated Evaluator + Pipeline Orchestrator

```
Build two files for [PROJECT_NAME].

FILE 1: scraper/evaluate_insights.py
Use claude-haiku-4-5-20251001 for cost efficiency. This model acts as quality auditor — different system prompt from the insight generator.

Evaluator system prompt:
You are a quality auditor for AI-generated sales intelligence. Score the insight on 4 dimensions and return only a JSON object. No commentary.
- relevance (0-1): Is this specific to this entity, or generic boilerplate that could apply to anyone?
- actionability (0-1): Does the next_action give the rep something specific and concrete to do?
- accuracy (0-1): Are all claims grounded in the input data? Penalize invented details not present in input.
- clarity (0-1): Is it written for a non-expert rep reading in 30 seconds, not a data analyst?

User prompt: Input data provided: [ENTITY FIELDS]. Generated insight: [ALL 5 FIELDS]. Return: {"relevance": float, "actionability": float, "accuracy": float, "clarity": float}

Pipeline:
- Query all insights with no evaluation record
- Batches of 20, semaphore(5)
- Write to evaluations table with evaluator="auto"
- overall_score = mean of 4 dimensions
- If overall_score < 0.6: set insight.flagged_for_review=True, flag_reason="auto_eval_low_score"
- Print: score histogram, % flagged, avg score by priority tier
- Export flagged to scraper/flagged_insights.json
Runnable as: python evaluate_insights.py [--all]

FILE 2: scraper/run_pipeline.py
Single entry point that runs all steps in order:
1. fetch_data.py
2. build_insights.py
3. evaluate_insights.py

Flags: --zip (required), --radius (default 10), --force-insights, --incremental (last 24h only), --skip-eval, --dry-run
End report: records fetched/new/updated, insights generated/flagged, total runtime, estimated API cost
Writes pipeline_runs record.
--report flag: print stats from last 5 runs without scraping.
Runnable as: python run_pipeline.py --zip 10013 --radius 10
```

---

### STEP 6B — Evaluation Doc + Presentation Deck

```
Write two documents for [PROJECT_NAME].

DOCUMENT 1: EVALUATION.md

## Automated Evaluation
- 4 scoring dimensions with exact rubrics and examples (what scores 0.2 vs 0.8 vs 1.0 on each dimension)
- Overall score formula: mean of 4 dimensions
- Flagging threshold: overall < 0.6 → flagged_for_review = true
- What happens to flagged insights: surfaced in manager dashboard, held from rep view until reviewed
- Cost estimate: ~500 tokens/eval × $0.00025/1k tokens × 1000 records = $0.13 for full evaluation pass
- How prompt_version enables A/B testing across prompt iterations

## Human-in-the-Loop Review
- Manager dashboard workflow step by step
- What to look for: generic talking points, invented facts, outdated data signals
- How rejections trigger regeneration: flag_reason="manager_rejected" → picked up by next pipeline run with --force-insights
- flag_reason categories: auto_eval_low_score, manager_rejected, outdated_data, missing_context, hallucinated_fact

## Continuous Improvement Loop
- A/B test: same 50 records, prompt_version A vs B, compare eval scores
- When to wipe and regenerate: major prompt change, data refresh older than 7 days
- Tracking: query evaluations grouped by prompt_version → plot avg score over versions

## Limitations
- LLM-as-judge reflects evaluator model's biases, not ground truth
- Accuracy scoring cannot verify claims against external sources
- Human review bottleneck at scale: triage approach — only human-review High priority flagged insights

---

DOCUMENT 2: PRESENTATION.md

Write a complete 1-hour live presentation script for [PROJECT_NAME]. Structure:

## Slide 1 — The Problem (5 min)
- What problem does [COMPANY/CLIENT] face with their current data/process
- Why existing tools fail (keyword search, manual research, spreadsheets)
- What a sales rep actually needs in the 30 seconds before a call
- Exact words to say

## Slide 2 — Live Demo (15 min)
- Walk through the rep dashboard: filtering, card selection, InsightPanel
- Read a talking_point out loud — explain why it is specific, not generic
- Show a risk alert — explain what triggers it
- Show the manager dashboard: flagged insights, summary stats
- Show export CSV
- Exact narration for each click

## Slide 3 — System Architecture (10 min)
- ASCII diagram: Browser → Next.js → FastAPI → SQLite | Claude API | [DATA_SOURCE] Scraper
- Explain each layer in one sentence
- Why FastAPI over Django/Flask (async, Pydantic, OpenAPI auto-docs)
- Why SQLite for demo, why Postgres for production (explain the migration path — it is one line change in DATABASE_URL)
- Why SSE or REST (explain the choice made)
- Exact words to say for each component

## Slide 4 — Data Pipeline (10 min)
- How the scraper works: the network request approach vs BeautifulSoup
- Why you chose this scraping method (cite: JS-rendered page, API found in DevTools)
- Pagination, concurrency (semaphore 5), retry logic — explain each decision
- Incremental refresh: why 24h TTL (balance freshness vs API cost)
- Data quality logging: what issues were found, how they are surfaced
- Exact words to say

## Slide 5 — AI Insights Engine (10 min)
- Why pre-computed not on-demand (explain: faster for reps, consistent, evaluatable)
- The 5 insight types and why each one matters to a sales rep
- Prompt design decisions: why one call not 5, why tool_use for structured output, why prompt caching
- Token cost math: X records × Y tokens × $Z/1k = total cost
- Exact words to say

## Slide 6 — Evaluation Framework (5 min)
- The 4 scoring dimensions and what each catches
- The flagging threshold and what happens to flagged insights
- Human-in-the-loop: manager review workflow
- How this enables prompt iteration over time
- Exact words to say

## Slide 7 — Scalability & Extensions (3 min)
- SQLite → Postgres: one environment variable change
- Adding a new territory: one CLI command
- Adding a new insight type: one field in the tool schema + one component
- What would require actual engineering: auth, CRM integration, real-time refresh
- Exact words to say

## Q&A Prep — Likely Questions With Verbatim Answers
List 8 questions the panel is likely to ask and exact answers:
1. Why not use OpenAI instead of Claude?
2. How do you handle data that changes frequently?
3. What happens if the scraper breaks when the site updates?
4. How would you scale this to 50 ZIP codes / 10,000 records?
5. Why SQLite and not Postgres from the start?
6. How do you know the AI insights are accurate?
7. What would you build next with two more weeks?
8. How would you handle auth and multi-user access?
```

---

## STEP 7 — Deployment
*Run after everything works locally.*

```
Set up full deployment for [PROJECT_NAME] and deploy it.

PART 1 — Config files

backend/Dockerfile:
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"

backend/.dockerignore:
__pycache__
*.pyc
.env
*.db
.git

railway.toml at repo root:
[build]
builder = "DOCKERFILE"
dockerfilePath = "backend/Dockerfile"
watchPatterns = ["backend/**"]
[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

frontend/.env.local.example:
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

PART 2 — Deploy steps (write these as a checklist in README.md)

Backend on Railway:
1. Push repo to GitHub
2. railway.app → New Project → Deploy from GitHub repo
3. Select repo, set Root Directory = backend
4. Variables tab → add: ANTHROPIC_API_KEY=[key], ALLOWED_ORIGINS=https://[your-vercel-url].vercel.app
5. Settings → Networking → Generate Domain → enter port 8080 (Railway assigns this)
6. Wait for build (~5 min first time). Check Deploy Logs — look for "Application startup complete"
7. Visit [railway-url]/health — should return {"status":"ok"}

Frontend on Vercel:
1. vercel.com → New Project → Import repo
2. Set Root Directory = frontend
3. Environment Variables → add: NEXT_PUBLIC_BACKEND_URL=https://[railway-url] (NO trailing slash)
4. Deploy. Visit the Vercel URL — UI should load.

Wire up CORS:
1. Copy the Vercel production URL (e.g. https://[project].vercel.app)
2. Railway → Variables → update ALLOWED_ORIGINS = https://[project].vercel.app
3. Railway auto-redeploys. Test a chat/query from the Vercel URL.

Common errors and fixes:
- "Failed to fetch" = CORS. Check ALLOWED_ORIGINS has no trailing slash.
- "//chat 404" = NEXT_PUBLIC_BACKEND_URL has trailing slash. Remove it, redeploy Vercel.
- OPTIONS 400 = Origin mismatch. ALLOWED_ORIGINS must exactly match browser Origin header.
- App failed to respond = check Deploy Logs for startup crash (usually missing env var).
- Build failed in 3 seconds = railway.toml not found at repo root (not inside backend/).

PART 3 — Run the pipeline against live data after deployment
Once Railway is running, SSH or use Railway's terminal to run:
python run_pipeline.py --zip [ZIP] --radius 10
This populates the database so the dashboard has real data.
```

---

## STEP 8 — README
*Takes 10 minutes.*

```
Write README.md at the repo root for [PROJECT_NAME].

Sections:
1. Project name + one-line description. Live demo: [URL]
2. Problem statement: 3 bullets from a sales rep's perspective
3. Features: 4 bullets for reps, 2 for managers
4. Architecture diagram (ASCII):
   Browser → Next.js (Vercel) → FastAPI (Railway) → SQLite
                                        ↓                ↑
                                  Claude claude-sonnet-4-6    [DATA_SOURCE] Scraper
5. Tech stack table: Layer | Technology | Why chosen
6. Data pipeline: scraping approach used, incremental refresh, data quality logging
7. AI insights: 5 types, evaluation framework in 3 sentences, cost estimate
8. Quick start: exact commands — backend, scraper, frontend
9. Environment variables table for both services
10. Project structure tree
11. Deployment: link to the step-by-step in this README or point to EVALUATION.md
12. Known limitations: [3 honest limitations]
13. What's next: [3 extensions ranked by effort]
```

---

## PARALLEL EXECUTION MAP — 4-Hour Timeline

```
TIME    WHAT                                    WHO DOES IT
0:00    Manual: network request capture         You (browser + DevTools)
0:20    Step 1: Scaffold                        Claude session 1
0:30    Step 2: Database schema                 Claude session 1
0:40    Step 3A: Scraper          ──────────── Claude session 1 (runs 30-45 min)
        Step 3B: Backend API      ──────────── Claude session 2 (runs 10 min)
1:00    Step 4A: Insights engine  ──────────── Claude session 2 (while 3A still runs)
        Step 4B: Frontend types + components ─ Claude session 3
1:50    Step 5: Dashboard pages                 Claude session 2 or 3
        (3A scraper likely done by now)
2:20    Step 6A: Evaluator + orchestrator ───── Claude session 2
        Step 6B: Eval doc + presentation ─────  Claude session 3
3:00    Step 7: Deployment                      Claude session 1
3:30    Step 8: README                          Claude session 1
3:45    Run pipeline against live data          You (Railway terminal)
4:00    Rehearse presentation                   You
```

---

## VARIABLES REFERENCE — Fill These In Before Starting

| Variable | Example (GAF) | Your value |
|----------|--------------|------------|
| [PROJECT_NAME] | gaf-sales-platform | |
| [ENTITY_NAME] | contractor | |
| [ENTITY_TYPE] | roofing contractor | |
| [DATA_SOURCE] | GAF contractor directory | |
| [COMPANY/INDUSTRY] | roofing product distributor | |
| [DOMAIN] | roofing products and contractor sales | |
| [MAIN_CATEGORY] | tier | |
| [KEY_FIELD_1] | tier | |
| [KEY_FIELD_2] | rating | |
| [FILTER_1] | tier | |
| [FILTER_2] | min_rating | |
| [ZIP_CODE] | 10013 | |

---

## 1-HOUR PRESENTATION STRUCTURE

```
0:00–0:05   Intro — who you are, what you built, live URL
0:05–0:20   Live demo — rep dashboard → filter → card → insight panel → manager view
0:20–0:30   Architecture slide — each layer, each decision
0:30–0:40   Data pipeline slide — scraping approach + why, incremental refresh, quality
0:40–0:50   AI + evaluation slide — 5 insight types, prompt design, scoring, flagging loop
0:50–0:55   Scalability slide — Postgres migration, new territories, new insight types
0:55–1:00   Q&A
```

---

## IF YOU RUN OUT OF TIME — Cut In This Order

1. Cut manager dashboard charts (keep flagged insights list)
2. Cut CSV export
3. Cut incremental refresh (full re-scrape only)
4. Cut docker-compose.yml
5. Cut search endpoint
6. NEVER cut: InsightPanel, FilterBar, talking_point field, automated evaluator, EVALUATION.md, the presentation deck
