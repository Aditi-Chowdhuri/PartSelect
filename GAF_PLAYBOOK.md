# GAF Sales Intelligence Platform — End-to-End Build Playbook

Complete prompt sequence to build this project in ~4 hours.
Run each prompt in order. Do not skip Phase 0 — the scraper cannot work without the real network request.

---

## Phase 0 — Capture the Network Request (Manual — Do This First)

Before running any prompt, you must capture the real API call GAF makes when you search contractors.

**Steps:**
1. Open https://www.gaf.com/en-us/roofing-contractors/residential in Chrome
2. Open DevTools → Network tab → filter by Fetch/XHR
3. Enter ZIP code `10013` in the search box and hit search
4. In the Network tab, find the request that returns contractor data (look for JSON responses with contractor names, addresses, ratings)
5. Right-click that request → Copy → Copy as cURL
6. Also note: the full URL, all headers (especially Authorization, x-api-key, or cookie), the request payload/body if it's a POST, and paste the full raw JSON response

**Give me all of the following before running Prompt 1:**
- The cURL command (or URL + headers + body)
- The raw JSON response for one page of results
- Whether it paginates (look for `page`, `offset`, `cursor`, or `total` fields in the response)

---

## Phase 1 — System Design (30 min)

### Prompt 1.1 — Project scaffold

```
Create the full project structure for a GAF sales intelligence platform. The stack is:
- Backend: FastAPI (Python), SQLite for dev (Postgres-ready schema)
- AI: Anthropic Claude claude-sonnet-4-6 for insight generation
- Frontend: Next.js 14, TypeScript, Tailwind CSS
- Scraper: Python with httpx and asyncio

Create this directory structure with all empty files in place:
gaf-sales-platform/
  backend/
    app/
      main.py
      models.py
      database.py
      scraper.py
      insights.py
      evaluator.py
      routers/
        contractors.py
        insights.py
        export.py
    requirements.txt
    .env.example
    Dockerfile
  frontend/
    src/
      app/
        page.tsx
        layout.tsx
      components/
        ContractorCard.tsx
        InsightPanel.tsx
        FilterBar.tsx
        PriorityBadge.tsx
        RiskAlert.tsx
        RepDashboard.tsx
        ManagerDashboard.tsx
      lib/
        api.ts
        types.ts
    package.json
    tailwind.config.ts
    .env.local.example
  scraper/
    fetch_contractors.py
    build_insights.py
    evaluate_insights.py
    run_pipeline.py
  README.md

After creating the structure, initialize the frontend with: npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir (adjust if src/ dir is needed). Then install backend deps.
```

---

### Prompt 1.2 — Database schema

```
Design and implement the SQLite database schema for the GAF sales platform. Write backend/app/database.py with SQLAlchemy ORM models.

Tables needed:

contractors:
  id (PK), gaf_id (unique), name, address, city, state, zip, phone, website,
  latitude, longitude, tier (MasterElite / Master / Certified / unknown),
  certifications (JSON array), rating (float), review_count (int),
  years_in_business (int), employee_count (int), last_activity_date (date),
  raw_json (text), created_at, updated_at, data_quality_issues (JSON array)

insights:
  id (PK), contractor_id (FK), generated_at,
  business_summary (text), talking_point (text), risk_alert (text),
  priority (High/Medium/Low), priority_reasoning (text),
  next_action (text), next_action_type (call/email/brochure/visit),
  insight_score (float 0-1), score_breakdown (JSON),
  model_used (text), prompt_version (text), flagged_for_review (bool),
  flag_reason (text)

evaluations:
  id (PK), insight_id (FK), evaluated_at, evaluator (auto/human),
  relevance_score (float), actionability_score (float),
  accuracy_score (float), clarity_score (float), overall_score (float),
  notes (text)

pipeline_runs:
  id (PK), run_at, zip_code, radius_miles, contractors_fetched,
  contractors_new, contractors_updated, insights_generated,
  errors (JSON array), duration_seconds (float)

Include: Alembic migration setup, a get_db() dependency, and an init_db() function that creates all tables. Make the schema Postgres-compatible (no SQLite-only types).
```

---

## Phase 2 — Data Scraper (45 min)

### Prompt 2.1 — Contractor scraper

```
Build the GAF contractor scraper in scraper/fetch_contractors.py.

Here is the real network request captured from GAF's website:
[PASTE YOUR CURL COMMAND HERE]

Here is a sample response page:
[PASTE THE RAW JSON RESPONSE HERE]

Build an async scraper that:
1. Accepts zip_code and radius_miles as parameters
2. Handles pagination using whatever field controls pages in the response (show me the field name from the JSON)
3. Uses httpx.AsyncClient with a semaphore of 5 concurrent requests
4. Retries failed requests up to 3 times with exponential backoff
5. Parses each contractor record into the contractors table schema
6. Detects and logs data quality issues: missing phone, missing rating, no reviews, missing address
7. Writes contractors to SQLite via SQLAlchemy, upserts on gaf_id (update if exists, insert if new)
8. Supports incremental refresh: only re-fetches contractors whose updated_at is older than 24 hours
9. Writes a pipeline_run record with counts and any errors

The scraper should be runnable as: python fetch_contractors.py --zip 10013 --radius 10

Output a progress bar (tqdm) and a final summary: X new, Y updated, Z errors.
```

---

### Prompt 2.2 — Data quality audit

```
After running the scraper, I need a data quality report. Add a function audit_data_quality() to scraper/fetch_contractors.py that:

1. Queries all contractors from the database
2. Reports:
   - Total contractors
   - % with phone numbers
   - % with ratings
   - % with review_count > 0
   - % with website
   - Breakdown by tier (MasterElite / Master / Certified / unknown)
   - Breakdown by city
   - Contractors with data_quality_issues (list the issues)
3. Prints a clean table to stdout
4. Writes a JSON report to scraper/data_quality_report.json

Run it as: python fetch_contractors.py --audit
```

---

## Phase 3 — AI Insights Engine (45 min)

### Prompt 3.1 — Insight generation

```
Build the AI insights engine in scraper/build_insights.py using Anthropic's Python SDK with Claude claude-sonnet-4-6.

For each contractor, generate a single structured JSON response containing all 5 insight fields in one API call (not 5 separate calls). Use prompt caching on the system prompt.

System prompt should establish the persona: a senior B2B sales strategist at a roofing product distributor, with deep knowledge of GAF certification tiers, roofing contractor business models, and what makes a strong vs weak sales prospect.

User prompt should include all available contractor fields: name, tier, certifications, rating, review_count, years_in_business, city, zip, website presence, last activity.

Required output schema (enforce with tool use or structured output):
{
  "business_summary": "2-3 sentences on scale, activity level, market position",
  "talking_point": "1 specific opening line for a cold call, referencing their actual tier/cert/rating",
  "risk_alert": "1 sentence — any red flag (low reviews, no recent activity, low rating, new business). Say 'None identified' if clean.",
  "priority": "High | Medium | Low",
  "priority_reasoning": "1 sentence explaining the priority rating",
  "next_action": "specific action with context",
  "next_action_type": "call | email | brochure | visit"
}

Additional requirements:
- Process in batches of 20 contractors
- Use asyncio to run 5 concurrent insight generations
- Skip contractors that already have insights generated in the last 24 hours (unless --force flag)
- Write results to the insights table
- Log token usage per batch
- Handle rate limits with exponential backoff

Run as: python build_insights.py --zip 10013 [--force]
```

---

### Prompt 3.2 — Automated evaluator

```
Build the automated insight evaluator in scraper/evaluate_insights.py.

For each generated insight, use a second Claude call (claude-haiku-4-5 to save cost) to score it on 4 dimensions. Use a different system prompt than the insight generator — this is the quality auditor persona.

Scoring prompt should evaluate:
- Relevance (0-1): Is the insight specific to this contractor, or could it apply to anyone?
- Actionability (0-1): Does the next action give a rep something concrete to do?
- Accuracy (0-1): Are all claims grounded in the data provided (no hallucinated facts)?
- Clarity (0-1): Is it written for a non-expert sales rep, not a data scientist?

Return scores as JSON. Overall score = average of 4 dimensions.

Logic:
- Score all insights that have no evaluation yet
- If overall_score < 0.6, set flagged_for_review = true on the insight and log it
- Write scores to the evaluations table
- Print a distribution: how many High/Medium/Low quality insights, average score by contractor tier
- Export flagged insights to scraper/flagged_insights.json for human review

Run as: python evaluate_insights.py [--all to re-evaluate everything]
```

---

## Phase 4 — Backend API (30 min)

### Prompt 4.1 — FastAPI routes

```
Build the complete FastAPI backend in backend/app/main.py and the router files.

backend/app/routers/contractors.py:
GET /contractors
  Query params: zip, radius_miles, priority (High/Medium/Low), tier, min_rating, has_risk_alert (bool), sort_by (priority_score/rating/review_count/name), limit, offset
  Returns: paginated list of contractors with their latest insight attached
  Include: total_count in response for pagination

GET /contractors/{id}
  Returns: full contractor record + latest insight + all evaluations

GET /contractors/search?q=
  Full-text search on name, city, address

backend/app/routers/insights.py:
POST /insights/{contractor_id}/regenerate
  Trigger re-generation of insight for one contractor
  Returns: new insight

PATCH /insights/{insight_id}/flag
  Body: { reason: string }
  Sets flagged_for_review = true

backend/app/routers/export.py:
GET /export/csv?zip=&priority=
  Returns CSV of contractors + insights for the given filters
  Columns: name, tier, rating, review_count, priority, talking_point, next_action, phone

GET /export/summary
  Returns aggregate stats: total contractors, breakdown by priority/tier, average scores

All routes must:
- Have response_model typed with Pydantic
- Include proper error handling (404, 422)
- Support CORS from localhost:3000 and the production Vercel URL (from ALLOWED_ORIGINS env var)
- Log request timing
```

---

### Prompt 4.2 — Pipeline orchestrator

```
Build scraper/run_pipeline.py as the single entry point that runs the full pipeline in order:

1. fetch_contractors.py — scrape and upsert contractors
2. build_insights.py — generate AI insights for new/stale contractors
3. evaluate_insights.py — score all un-evaluated insights
4. Print a final pipeline report: contractors fetched, insights generated, insights flagged, total runtime, estimated API cost

Accept flags:
--zip (required)
--radius (default 10)
--force-insights (regenerate even if fresh)
--skip-eval (skip evaluation step)

Write a pipeline_runs record at the end.

Also add an incremental mode (--incremental): only process contractors updated in the last 24 hours and insights generated in the last 24 hours.
```

---

## Phase 5 — Frontend Dashboard (45 min)

### Prompt 5.1 — Types and API client

```
Build frontend/src/lib/types.ts and frontend/src/lib/api.ts.

types.ts should define:
- Contractor (all fields from the DB schema)
- Insight (all fields)
- Evaluation
- ContractorWithInsight (Contractor + latest Insight)
- Priority type ("High" | "Medium" | "Low")
- FilterState { zip, priority, tier, minRating, hasRiskAlert, sortBy, search }
- PaginatedResponse<T> { items: T[], total: number, page: number, pageSize: number }

api.ts should implement:
- getContractors(filters: FilterState, page: number): Promise<PaginatedResponse<ContractorWithInsight>>
- getContractor(id: number): Promise<ContractorWithInsight>
- searchContractors(query: string): Promise<ContractorWithInsight[]>
- regenerateInsight(contractorId: number): Promise<Insight>
- flagInsight(insightId: number, reason: string): Promise<void>
- exportCSV(filters: FilterState): void (triggers download)
- getSummary(): Promise<SummaryStats>

Use NEXT_PUBLIC_BACKEND_URL env var. All fetch calls should handle errors and return typed responses.
```

---

### Prompt 5.2 — Core components

```
Build the frontend components in frontend/src/components/.

PriorityBadge.tsx:
- Props: priority: "High" | "Medium" | "Low"
- High = red pill, Medium = amber pill, Low = gray pill
- Small, compact, used inline

RiskAlert.tsx:
- Props: alert: string | null
- If null or "None identified" render nothing
- Otherwise render an amber warning banner with an exclamation icon
- Keep it compact — one line max

InsightPanel.tsx:
- Props: insight: Insight, onFlag: () => void, onRegenerate: () => void
- Shows: business_summary, talking_point (highlighted in a callout box — "Use this on the call"), risk_alert (via RiskAlert component), next_action with next_action_type icon
- Footer: insight_score as a thin progress bar, "Flag for review" button, "Regenerate" button
- Entire panel fits in a right-side drawer — max 400px wide

ContractorCard.tsx:
- Props: contractor: ContractorWithInsight, onClick: () => void, selected: boolean
- Shows: name, tier badge, city, rating (stars), review_count, PriorityBadge, one-line business_summary
- Selected state has an orange left border
- Compact — fits 6-8 cards on screen without scrolling

FilterBar.tsx:
- Controls: ZIP input, Priority multi-select, Tier multi-select, Min rating slider, Risk alert toggle, Sort by dropdown, Search input
- Inline layout — single row on desktop
- On change, calls onFilterChange callback immediately (no submit button)
```

---

### Prompt 5.3 — Dashboards and pages

```
Build the main dashboard pages.

frontend/src/app/page.tsx — Rep Dashboard (default view):
Layout: FilterBar at top, ContractorCard list on left (scrollable, 40% width), InsightPanel drawer on right (60% width, opens when card clicked).

Behaviour:
- On load, fetch contractors for default filters (zip=10013, sort by priority)
- Clicking a card opens its InsightPanel on the right
- Keyboard: arrow keys navigate cards, Escape closes panel
- Infinite scroll or pagination at bottom of card list
- "Export CSV" button in top right
- Show total count: "Showing 24 of 87 contractors"

RepDashboard.tsx sub-component — "Quick Stats" bar between FilterBar and card list:
- Total contractors in view
- High priority count (red)
- Contractors with risk alerts (amber)
- Average insight score

frontend/src/app/manager/page.tsx — Manager Dashboard:
- Table view instead of cards: sortable columns for name, tier, rating, priority, insight_score, flagged
- Flagged insights section at top: list of contractors with flagged=true, flag reason, "Mark reviewed" button
- Aggregate charts (use recharts): priority distribution pie, tier breakdown bar, average score by tier
- Bulk actions: select multiple → Export CSV, Regenerate insights

Both pages should be clean, minimal, and work at 1280px+ width. Use gray-900 as primary text, a professional blue (#1e40af) as accent (this is a B2B tool, not consumer).
```

---

## Phase 6 — Evaluation Framework Doc (15 min)

### Prompt 6.1 — Evaluation documentation

```
Write a comprehensive EVALUATION.md at the project root documenting the insight evaluation framework.

Cover:

1. Automated Evaluation
- The 4 scoring dimensions (relevance, actionability, accuracy, clarity) with definitions and rubrics
- How scores are calculated and aggregated
- Threshold for flagging (overall < 0.6)
- How flagged insights are handled (held from reps, queued for regeneration)
- Token cost estimate for running evaluation at scale (1000 contractors)

2. Human-in-the-Loop Review
- Manager dashboard workflow: how flagged insights surface
- What a manager reviews and approves/rejects
- How rejections feed back into prompt refinement
- The flag_reason field and what categories of issues it captures

3. Continuous Improvement Loop
- How prompt_version field tracks which prompt generated each insight
- A/B testing approach: run two prompt versions on same contractors, compare eval scores
- When to trigger full regeneration vs incremental

4. Metrics to Track Over Time
- Average insight score by tier
- % flagged per pipeline run
- Score improvement over prompt versions
- Rep engagement (which insights get used — future instrumentation hook)

5. Known Limitations
- LLM evaluation is not ground truth — it reflects the evaluator model's biases
- Accuracy scoring is limited since we cannot verify claims against external sources
- Human review bottleneck at scale

Write this as a professional document a hiring team would read. No fluff, concrete and specific.
```

---

## Phase 7 — Deployment (20 min)

### Prompt 7.1 — Docker and deployment config

```
Set up the full deployment configuration for this project.

backend/Dockerfile:
- python:3.11-slim base
- Install requirements
- Copy app files
- CMD uses $PORT env var: sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"

railway.toml at repo root:
- builder = DOCKERFILE
- dockerfilePath = backend/Dockerfile
- healthcheckPath = /health
- watchPatterns = ["backend/**"]

backend/.env.example:
ANTHROPIC_API_KEY=
ALLOWED_ORIGINS=http://localhost:3000
DATABASE_URL=sqlite:///./gaf.db

frontend/.env.local.example:
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

Add GET /health to FastAPI that returns {"status": "ok", "contractors": <count>, "insights": <count>}.

Also write a docker-compose.yml at the root that runs backend + a simple volume-mounted SQLite for local dev.

Deployment instructions:
- Backend: Railway (Dockerfile builder, root directory = backend)
- Frontend: Vercel (root directory = frontend, set NEXT_PUBLIC_BACKEND_URL to Railway URL)
- ALLOWED_ORIGINS on Railway = Vercel production URL
```

---

### Prompt 7.2 — README

```
Write a comprehensive README.md at the repo root for the GAF Sales Intelligence Platform.

Include:
1. One-line description and live demo URL (placeholder)
2. Screenshot placeholder
3. Features list: what a rep can do, what a manager can do
4. Architecture diagram (ASCII): Browser → Next.js → FastAPI → SQLite | Claude API | GAF Scraper
5. Tech stack table: layer, technology, why chosen
6. Data pipeline explanation: how GAF data is fetched, what the Wayback approach is NOT used here (live API), incremental refresh logic
7. AI insights explanation: the 5 insight types, the evaluation framework summary
8. Quick start: backend setup, scraper run, frontend setup — exact commands
9. Environment variables for both frontend and backend
10. Project structure tree
11. Evaluation framework summary (link to EVALUATION.md)
12. Known limitations and extensions

Make it look like a polished open-source project. Use clear headers, tables, and code blocks. No fluff.
```

---

## Phase 8 — Loom Video Script (10 min)

### Prompt 8.1 — Loom walkthrough script

```
Write a tight 5-minute Loom video script for presenting the GAF Sales Intelligence Platform. Structure it as:

00:00–00:30 — The problem in one sentence. Show the GAF contractor directory page.
00:30–01:30 — Live demo: Rep dashboard. Filter by High priority, show a ContractorCard, click to open InsightPanel. Read the talking point out loud. Point to the risk alert. Show the next action.
01:30–02:00 — Demo: Search by contractor name. Show the export CSV button.
02:00–02:30 — Manager dashboard: show the flagged insights list, the priority distribution chart.
02:30–03:30 — Architecture walkthrough (30 seconds each): data pipeline → AI engine → evaluation loop → API → frontend.
03:30–04:00 — Evaluation framework: explain the 4 scoring dimensions and what happens when score < 0.6.
04:00–04:30 — Extensibility: adding a new ZIP, scaling to Postgres, adding a new insight type.
04:30–05:00 — Close: what I would build next with more time.

For each section, write the exact words to say. Keep it confident, technical but accessible. No filler phrases like "so basically" or "um".
```

---

## Prompt Cheat Sheet — 4-Hour Timeline

| Time | Prompt | Output |
|------|--------|--------|
| 0:00 | Phase 0 | Network request captured manually |
| 0:15 | 1.1 | Project scaffold created |
| 0:25 | 1.2 | Database schema done |
| 0:35 | 2.1 | Scraper running, data in DB |
| 0:55 | 2.2 | Data quality report printed |
| 1:05 | 3.1 | Insights generated for all contractors |
| 1:35 | 3.2 | Evaluation scores in DB, flagged list exported |
| 1:55 | 4.1 | All API routes working |
| 2:15 | 4.2 | Pipeline orchestrator working end-to-end |
| 2:30 | 5.1 | Frontend types and API client done |
| 2:45 | 5.2 | All components built |
| 3:15 | 5.3 | Both dashboards working |
| 3:45 | 6.1 | EVALUATION.md written |
| 3:55 | 7.1 | Docker + deployment config done |
| 4:05 | 7.2 | README done |
| 4:15 | 8.1 | Loom script ready |

---

## Key Decisions to Make Before Starting

1. **Will you use SQLite or Postgres?** SQLite is faster to set up. Switch to Postgres for the submission if you want to impress on scalability.
2. **Will you pre-generate all insights or generate on demand?** Pre-generate — the case study explicitly says "pre-computed sales intelligence."
3. **Will the evaluator use Claude Haiku or Sonnet?** Haiku for cost, Sonnet if quality matters more.
4. **Do you need auth?** No — skip auth entirely, it wastes time.
5. **Recharts or another chart lib?** Recharts is the lightest, easiest with Next.js.

---

## If You Run Out of Time — Cut In This Order

1. Cut the Manager Dashboard (keep Rep Dashboard only)
2. Cut the evaluation charts (keep the flagged insights list)
3. Cut the CSV export
4. Cut the scraper incremental refresh (just full re-scrape)
5. Never cut: the InsightPanel, the FilterBar, the automated evaluator, EVALUATION.md
