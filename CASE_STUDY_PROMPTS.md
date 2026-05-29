# Case Study Build Prompts — Copy-Paste Playbook

Generic prompt sequence for any AI-powered data pipeline + insights + dashboard case study.
Replace bracketed values before pasting. Parallel steps are marked — open a second Claude session and run both at the same time.

---

## BEFORE YOU START — Manual Step (Required)

Open the data source website in Chrome. Open DevTools → Network tab → XHR/Fetch filter. Trigger a search or page load that returns the data you need to scrape. Find the JSON response. Right-click the request → Copy as cURL.

You need four things before running any prompt:
1. The full cURL command (URL + headers + body)
2. A sample JSON response (paste the raw text)
3. Whether it paginates and what field controls the page (look for: page, offset, cursor, total, nextPageToken)
4. Any auth headers (Authorization, x-api-key, cookie) — note if they expire

Do not run Prompt 1 until you have all four.

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
2. Run: cd [PROJECT_NAME]/backend && pip install fastapi uvicorn sqlalchemy httpx anthropic python-dotenv tqdm alembic pydantic asyncio aiofiles
3. Write backend/requirements.txt with all installed packages pinned to current versions

Confirm every file and directory exists when done.
```

---

## STEP 2 — Database Schema
*Run after Step 1. Takes 5 minutes.*

```
Write the complete SQLAlchemy ORM database schema in backend/app/database.py for [PROJECT_NAME].

The main data entity is [ENTITY_NAME] (e.g. contractor, property, listing, company). For each record we store:
- Raw data fields from the source: [LIST_YOUR_FIELDS — e.g. name, address, city, zip, phone, rating, review_count, tier, certifications, website, latitude, longitude]
- Metadata: source_id (unique, from the scraped source), raw_json (full original response), created_at, updated_at, data_quality_issues (JSON array of strings)

The insights table stores AI-generated intelligence per entity:
- entity_id (FK), generated_at, model_used, prompt_version
- business_summary (text)
- talking_point (text)
- risk_alert (text)
- priority (High / Medium / Low)
- priority_reasoning (text)
- next_action (text)
- next_action_type (call / email / brochure / visit)
- insight_score (float 0-1)
- score_breakdown (JSON)
- flagged_for_review (bool, default false)
- flag_reason (text, nullable)

The evaluations table stores automated + human quality scores per insight:
- insight_id (FK), evaluated_at, evaluator (auto / human)
- relevance_score, actionability_score, accuracy_score, clarity_score, overall_score (all float 0-1)
- notes (text)

The pipeline_runs table logs every scraper execution:
- run_at, zip_code (or equivalent territory identifier), radius
- records_fetched, records_new, records_updated
- insights_generated, insights_flagged
- errors (JSON array), duration_seconds

Requirements:
- Use SQLAlchemy 2.0 declarative style
- Add a get_db() FastAPI dependency
- Add init_db() that creates all tables
- Add an upsert helper: upsert_entity(session, data: dict) that inserts or updates on source_id
- Make all types Postgres-compatible (no SQLite-only syntax)
- Write backend/app/models.py with matching Pydantic response schemas for all tables
```

---

## STEP 3A + 3B — Run These Two in Parallel
*Open two Claude sessions. Paste 3A in one, 3B in the other. Start both at the same time.*
*3A takes 30-45 minutes (scraping). 3B takes 10 minutes. Continue to Step 4 once 3B is done — do not wait for 3A.*

---

### STEP 3A — Data Scraper (Long-running — start first)

```
Build the async data scraper in scraper/fetch_data.py for [PROJECT_NAME].

Here is the real network request I captured:
--- PASTE YOUR FULL CURL COMMAND HERE ---

Here is a sample JSON response:
--- PASTE THE RAW JSON RESPONSE HERE ---

The pagination field is: [PASTE THE FIELD NAME — e.g. "page", "offset", "cursor"]
Total records field: [PASTE — e.g. "total", "totalResults", "count"]

Build a scraper that:
1. Accepts --zip [ZIP_CODE] --radius [MILES] as CLI args (or equivalent territory params)
2. Handles pagination: fetches all pages until no more results
3. Uses httpx.AsyncClient with connection pooling and a semaphore limiting to 5 concurrent requests
4. Retries failed requests up to 3 times with exponential backoff (1s, 3s, 9s)
5. Parses each record into the database schema using the upsert_entity helper
6. Logs data quality issues per record: which fields are missing or anomalous
7. Supports incremental refresh: skips records updated in the last 24 hours unless --force is passed
8. Shows a tqdm progress bar with current page / total pages
9. Writes a pipeline_runs record at the end with all counts
10. Prints a summary table at the end: X new, Y updated, Z skipped, W errors

Make it runnable as: python fetch_data.py --zip 10013 --radius 10

If rate limited (429), back off 60 seconds and retry. Log every error with the record ID and reason.
```

---

### STEP 3B — FastAPI Backend (Run in parallel with 3A)

```
Build the complete FastAPI backend for [PROJECT_NAME].

backend/app/main.py:
- Initialize FastAPI app with title, version, description
- Add CORSMiddleware: allow_origins from ALLOWED_ORIGINS env var (comma-separated), allow all methods and headers, allow_credentials=True
- Add request timing middleware that logs method + path + duration
- Include all three routers: data, insights, export
- Add GET /health that returns {"status": "ok", "record_count": <int>, "insight_count": <int>}
- Call init_db() on startup

backend/app/routers/data.py:
GET /[entities] — paginated list with filters:
  - territory (zip or equivalent)
  - priority (High/Medium/Low)
  - [RELEVANT_FILTER_1 — e.g. tier, category, type]
  - [RELEVANT_FILTER_2 — e.g. min_rating, min_score]
  - has_alert (bool)
  - sort_by (priority/rating/name/created_at)
  - search (text search on name and address)
  - page, page_size (default 20)
  Returns: { items: [...], total: int, page: int, page_size: int }
  Each item includes its latest insight if one exists.

GET /[entities]/{id} — full record + latest insight + all evaluations

backend/app/routers/insights.py:
POST /insights/{entity_id}/regenerate — trigger fresh insight generation for one record
PATCH /insights/{insight_id}/flag — body: { reason: string } — sets flagged_for_review = true
GET /insights/flagged — returns all flagged insights with entity info

backend/app/routers/export.py:
GET /export/csv — accepts same filters as the main list endpoint, returns CSV download
  Columns: name, [key fields], priority, talking_point, next_action, phone/contact
GET /export/summary — aggregate stats: total records, breakdown by priority, breakdown by [MAIN_CATEGORY], average insight score, count flagged

All routes: typed Pydantic response_model, proper 404/422 error handling, async database access.

Write backend/.env.example:
ANTHROPIC_API_KEY=
ALLOWED_ORIGINS=http://localhost:3000
DATABASE_URL=sqlite:///./[project].db
```

---

## STEP 4A + 4B — Run These Two in Parallel
*Start both as soon as Step 3B is done. Do not wait for 3A (scraping) to finish.*

---

### STEP 4A — AI Insights Engine

```
Build the AI insights engine in scraper/build_insights.py for [PROJECT_NAME].

Use the Anthropic Python SDK with Claude claude-sonnet-4-6. Generate all 5 insight fields in a single API call per record using tool_use to enforce structured output. Enable prompt caching on the system prompt.

SYSTEM PROMPT (write this carefully):
You are a senior B2B sales strategist for [COMPANY/INDUSTRY]. You specialize in [DOMAIN — e.g. roofing products, SaaS, industrial equipment]. Your job is to analyze [ENTITY_TYPE] records and generate actionable pre-call intelligence for sales representatives. You write concisely — reps read your output in 30 seconds before a call. Never fabricate data not present in the input. If a field is missing, work with what you have.

USER PROMPT template (fill fields from DB record):
Analyze this [ENTITY_NAME] and generate sales intelligence:
Name: {name}
[KEY_FIELD_1 — e.g. Tier/Category]: {tier}
[KEY_FIELD_2 — e.g. Rating]: {rating} ({review_count} reviews)
[KEY_FIELD_3 — e.g. Certifications]: {certifications}
[KEY_FIELD_4 — e.g. Years in business]: {years}
Location: {city}, {zip}
Website: {website or "none"}

Tool definition (enforce this output schema):
{
  "business_summary": "2-3 sentences: scale, activity level, market position",
  "talking_point": "one specific cold-call opening line referencing their actual data",
  "risk_alert": "one sentence red flag, or 'None identified'",
  "priority": "High | Medium | Low",
  "priority_reasoning": "one sentence explanation",
  "next_action": "specific recommended action with context",
  "next_action_type": "call | email | brochure | visit"
}

Pipeline logic:
- Query all records with no insight, or insight older than 48 hours (skip if --no-force and insight is fresh)
- Process in batches of 20
- Use asyncio.gather with semaphore(5) for 5 concurrent calls
- Write each result to the insights table immediately (don't wait for full batch)
- Log token usage per batch and running total cost estimate
- Handle 429/529 with exponential backoff: wait 60s on 429, 30s on 529
- At the end: print total generated, total skipped, total tokens used, estimated cost

Runnable as: python build_insights.py --zip 10013 [--force]
```

---

### STEP 4B — Frontend Types and Components

```
Build the complete frontend component library for [PROJECT_NAME].

frontend/src/lib/types.ts:
Define TypeScript interfaces for all data shapes:
- [EntityName] (all DB fields)
- Insight (all insight fields)
- Evaluation
- [EntityName]WithInsight (entity + latest insight)
- Priority = "High" | "Medium" | "Low"
- NextActionType = "call" | "email" | "brochure" | "visit"
- FilterState { territory, priority, [FILTER_1], [FILTER_2], hasAlert, sortBy, search, page }
- PaginatedResponse<T> { items: T[], total: number, page: number, page_size: number }
- SummaryStats { total: number, by_priority: Record<Priority, number>, by_[CATEGORY]: Record<string, number>, avg_score: number, flagged: number }

frontend/src/lib/api.ts:
const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL (no trailing slash)
Implement typed fetch wrappers:
- getEntities(filters: FilterState): Promise<PaginatedResponse<[EntityName]WithInsight>>
- getEntity(id: number): Promise<[EntityName]WithInsight>
- searchEntities(q: string): Promise<[EntityName]WithInsight[]>
- regenerateInsight(entityId: number): Promise<Insight>
- flagInsight(insightId: number, reason: string): Promise<void>
- getFlagged(): Promise<[EntityName]WithInsight[]>
- getSummary(): Promise<SummaryStats>
- exportCSV(filters: FilterState): void — builds URL with query params, triggers window.location download

frontend/src/components/PriorityBadge.tsx:
Props: priority: Priority. Render a colored pill. High=red, Medium=amber, Low=gray. Small and inline.

frontend/src/components/AlertBanner.tsx:
Props: alert: string | null. Render nothing if null or "None identified". Otherwise render a compact amber warning row with an icon.

frontend/src/components/InsightPanel.tsx:
Props: entity: [EntityName]WithInsight, onFlag: (reason: string) => void, onRegenerate: () => void
Layout (fits in a 420px right panel):
- Header: entity name + PriorityBadge
- "Use this on the call" callout box (light orange background): talking_point
- Business summary paragraph
- AlertBanner for risk_alert
- Next action row: icon (phone/email/gift/map) + next_action text
- Footer: insight_score as a labeled thin bar, timestamp, Flag button (opens a reason input), Regenerate button (spinner while loading)

frontend/src/components/DataCard.tsx:
Props: entity: [EntityName]WithInsight, selected: boolean, onClick: () => void
Compact card (fits 6+ on screen): name, [KEY_FIELD] badge, city, rating stars, PriorityBadge, one-line business_summary truncated. Orange left border when selected.

frontend/src/components/FilterBar.tsx:
Props: filters: FilterState, onChange: (f: FilterState) => void
Single-row layout on desktop: territory input, Priority checkboxes, [FILTER_1] dropdown, [FILTER_2] slider or toggle, Alert toggle, Sort dropdown, Search input. Every change fires onChange immediately.
```

---

## STEP 5 — Dashboard Pages
*Run after Step 4B is done.*

```
Build the main dashboard pages for [PROJECT_NAME].

frontend/src/app/page.tsx — Primary Rep Dashboard:

Layout: FilterBar pinned at top. Below it: left column (38%) = scrollable DataCard list with total count header. Right column (62%) = InsightPanel (empty state when nothing selected).

Behaviour:
- On mount, call getEntities with default filters, display results
- Clicking a DataCard opens that entity's InsightPanel on the right and marks card as selected
- Filtering: any FilterBar change calls getEntities with updated filters, resets to page 1
- Pagination: "Load more" button at bottom of card list (or infinite scroll)
- Top-right actions: "Export CSV" button, "Summary" stat chips (total shown, High priority count, alerts count)
- Keyboard: up/down arrows navigate cards, Escape deselects

frontend/src/app/manager/page.tsx — Manager Dashboard:

Top section — Flagged Insights:
- Calls getFlagged() on mount
- Shows a dismissable list: entity name, flag_reason, insight snippet, "Mark Reviewed" button (calls flagInsight with reason "reviewed_by_manager")
- If empty, show a green "No flagged insights" message

Middle section — Summary Stats (calls getSummary()):
- 4 stat cards: Total records, High priority count, Avg insight score, Flagged count
- Priority distribution: 3 colored bars (no chart library needed — plain Tailwind divs with widths as percentages)
- [MAIN_CATEGORY] breakdown: similar bar chart

Bottom section — Full Table View:
- Sortable columns: name, [CATEGORY], rating, priority, insight_score, flagged status
- Click a row to open a modal with the full InsightPanel
- Bulk select checkboxes → Export CSV for selected records
- "Regenerate" button per row

Navigation: add a minimal top nav with "Rep View" and "Manager View" links.

Design system for this project (B2B tool, not consumer):
- Primary text: gray-900
- Accent / interactive: blue-700 (#1d4ed8)
- High priority: red-600, Medium: amber-500, Low: gray-400
- Background: gray-50, Cards: white with gray-200 border
- Font: system font stack, no custom fonts needed
```

---

## STEP 6A + 6B — Run These Two in Parallel
*Start both once Step 5 is done.*

---

### STEP 6A — Automated Evaluator

```
Build the automated insight evaluator in scraper/evaluate_insights.py for [PROJECT_NAME].

Use claude-haiku-4-5-20251001 (cheaper, faster) for evaluation calls. This is a separate model acting as quality auditor.

System prompt for the evaluator:
You are a quality auditor for AI-generated sales intelligence. You evaluate insights on 4 dimensions and return only a JSON score object — no commentary.

Scoring rubric:
- relevance (0-1): Is the insight specific to this entity, or generic boilerplate that could apply to anyone?
- actionability (0-1): Does the next_action give the sales rep something concrete and specific to do?
- accuracy (0-1): Are all claims in the insight grounded in the input data? Penalize any detail not present in the input.
- clarity (0-1): Is it written for a non-expert rep who reads it in 30 seconds, not a data analyst?

User prompt template:
Rate this insight. Input data: [PASTE ENTITY FIELDS]. Generated insight: [PASTE ALL 5 FIELDS].
Return: {"relevance": float, "actionability": float, "accuracy": float, "clarity": float}

Pipeline logic:
- Query all insights with no evaluation record yet
- Run evaluations in batches of 20 with semaphore(5)
- Write evaluation to evaluations table with evaluator="auto"
- Compute overall_score = average of 4 dimensions
- If overall_score < 0.6: set insight.flagged_for_review = true, insight.flag_reason = "auto_eval_low_score"
- Print a summary: score distribution histogram, % flagged, average by priority tier
- Export all flagged insights to scraper/flagged_insights.json

Runnable as: python evaluate_insights.py [--all to re-evaluate everything]
```

---

### STEP 6B — Evaluation Documentation

```
Write EVALUATION.md at the project root for [PROJECT_NAME].

This is a required deliverable. Write it as a professional document a senior engineer or hiring manager would read. Be specific and concrete — no generic statements.

Structure:

## Automated Evaluation
- The 4 scoring dimensions with exact definitions and examples of what scores 0.2 vs 0.8 vs 1.0
- How overall_score is computed
- The flagging threshold (0.6) and what happens to flagged insights (held from reps? regenerated? queued?)
- Estimated cost to evaluate 1,000 records using claude-haiku-4-5-20251001 (compute from ~500 tokens/call × $0.00025/1k)
- How prompt_version field enables comparing evaluation scores across prompt iterations

## Human-in-the-Loop Review
- The manager dashboard workflow step by step
- What specifically a manager reviews (not just "reviews the insight" — what do they look for?)
- How a manager rejection feeds back: does it trigger regeneration? Does it update the prompt?
- The flag_reason field categories: auto_eval_low_score, manager_rejected, outdated_data, [add 2 more]

## Continuous Improvement Loop
- How to run an A/B test: same 50 records, prompt version A vs B, compare average eval scores
- Trigger for full regeneration: when to wipe and redo all insights (prompt change, data refresh)
- How to track score improvement over time (query evaluations table grouped by prompt_version)

## Limitations
- LLM-as-judge is not ground truth — it reflects the evaluator model's priors
- Accuracy scoring is weak without external ground truth to verify claims against
- Human review creates a bottleneck at scale — describe a tiered approach (auto for most, human for High priority flagged)

## Metrics Dashboard (Future)
- Rep engagement rate: which insights get acted on (requires CRM integration)
- Insight staleness: records with insights older than 7 days
- Coverage: % of records with a current insight
```

---

## STEP 7 — Pipeline Orchestrator
*Run after Steps 6A is done.*

```
Build scraper/run_pipeline.py as the single entry point for [PROJECT_NAME].

It runs the full pipeline in order:
1. fetch_data.py — scrape and upsert records
2. build_insights.py — generate AI insights for new/stale records
3. evaluate_insights.py — score all un-evaluated insights

Accept CLI flags:
  --zip (or --territory) — required
  --radius — default 10
  --force-insights — regenerate insights even if fresh
  --incremental — only process records updated in last 24h
  --skip-eval — skip evaluation step
  --dry-run — print what would run but don't execute

At the end, print a pipeline report:
  Records fetched / new / updated
  Insights generated / skipped
  Insights evaluated / flagged
  Total runtime
  Estimated API cost (tokens × price)

Write a pipeline_runs record to the database with all of these numbers.

Also add a --report flag that just prints stats from the last 5 pipeline_runs without running anything.

Runnable as: python run_pipeline.py --zip 10013 --radius 10
```

---

## STEP 8 — Deployment
*Run after everything is working locally.*

```
Set up the complete deployment configuration for [PROJECT_NAME].

backend/Dockerfile:
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"

backend/.dockerignore:
__pycache__, *.pyc, .env, *.db, .git

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

backend/.env.example:
ANTHROPIC_API_KEY=
ALLOWED_ORIGINS=http://localhost:3000
DATABASE_URL=sqlite:///./[project].db

frontend/.env.local.example:
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

Deployment instructions to include in README:
Backend → Railway: connect repo, root directory = backend, add ANTHROPIC_API_KEY and ALLOWED_ORIGINS env vars
Frontend → Vercel: connect repo, root directory = frontend, add NEXT_PUBLIC_BACKEND_URL = Railway service URL (no trailing slash)
After both deploy: update ALLOWED_ORIGINS on Railway to the Vercel production URL, redeploy Railway

Also write a docker-compose.yml at the repo root for local development:
- backend service: build from ./backend, port 8000, volume mount for SQLite persistence
- No frontend service needed (run with npm run dev separately)
```

---

## STEP 9 — README and Loom Script

```
Write README.md at the repo root for [PROJECT_NAME]. Then write a 5-minute Loom video script.

README.md sections:
1. One-line description. Live demo URL placeholder.
2. What it does — 4 bullet points from the rep's perspective, 2 from the manager's
3. Architecture diagram (ASCII): Browser → Next.js → FastAPI → SQLite | Claude API | [DATA_SOURCE] Scraper
4. Tech stack table: Layer | Technology | Why
5. Data pipeline: how data is fetched, incremental refresh, data quality logging
6. AI insights: the 5 insight types, the evaluation framework in 3 sentences
7. Quick start: exact commands to run backend, run scraper, run frontend
8. Environment variables table for both services
9. Project structure tree
10. Evaluation framework: link to EVALUATION.md

Loom script (5 minutes, write exact words to say):
0:00–0:30 The problem. Show the raw data source website. One sentence on why keyword search fails.
0:30–1:30 Rep dashboard live demo. Filter by High priority. Click a card. Read the talking point out loud. Point to the risk alert. Show the next action.
1:30–2:00 Show search, CSV export.
2:00–2:30 Manager dashboard: flagged insights, summary stats, table view.
2:30–3:30 Architecture: data pipeline → AI engine → evaluation loop → API → frontend. 30 seconds each.
3:30–4:00 Evaluation framework: the 4 dimensions, what happens when score < 0.6.
4:00–4:30 Extensibility: adding a new territory, scaling to Postgres, adding a new insight type.
4:30–5:00 What I would build next with more time.

Write the script as the exact words to say, not bullet points.
```

---

## PARALLEL EXECUTION MAP

```
Timeline (4 hours):

00:00  Manual: Capture network request
00:20  Step 1: Scaffold
00:30  Step 2: Database schema
00:40  START PARALLEL:
         Session A → Step 3A: Scraper (runs 30-45 min in background)
         Session B → Step 3B: Backend API
01:10  Session B done → START PARALLEL:
         Session A: still scraping (let it run)
         Session B → Step 4A: Insights engine
         Session C → Step 4B: Frontend types + components
02:00  Steps 4A + 4B done → Step 5: Dashboard pages
02:30  Step 5 done → START PARALLEL:
         Session B → Step 6A: Evaluator
         Session C → Step 6B: Evaluation docs
         Check if 3A (scraper) is done — if yes, run build_insights.py
03:00  Steps 6A + 6B done → Step 7: Pipeline orchestrator
03:20  Step 7 done → Step 8: Deployment
03:40  Step 8 done → Step 9: README + Loom script
04:00  Record Loom video
```

---

## VARIABLES REFERENCE — Fill These In Before Starting

| Variable | Example (GAF case) | Your value |
|----------|-------------------|------------|
| [PROJECT_NAME] | gaf-sales-platform | |
| [ENTITY_NAME] | contractor | |
| [ENTITY_TYPE] | roofing contractor | |
| [DATA_SOURCE] | GAF contractor directory | |
| [COMPANY/INDUSTRY] | roofing product distributor | |
| [DOMAIN] | roofing products and contractor sales | |
| [MAIN_CATEGORY] | tier | |
| [KEY_FIELD_1] | tier | |
| [KEY_FIELD_2] | rating | |
| [KEY_FIELD_3] | certifications | |
| [KEY_FIELD_4] | years in business | |
| [FILTER_1] | tier | |
| [FILTER_2] | min_rating | |
| [RELEVANT_FILTER_1] | tier | |
| [RELEVANT_FILTER_2] | min_rating | |
| [ZIP_CODE] | 10013 | |

---

## IF YOU RUN OUT OF TIME — Cut In This Order

1. Cut manager dashboard charts (keep the flagged insights list)
2. Cut CSV export endpoint
3. Cut incremental refresh in scraper (full re-scrape only)
4. Cut docker-compose.yml
5. NEVER cut: InsightPanel, FilterBar, automated evaluator, EVALUATION.md, the talking_point field
