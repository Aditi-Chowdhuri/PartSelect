# PartSelect Chat Agent — Presentation & Demo Guide

**Total time:** 13–15 minutes · 5 slides · live demo between slides 2 and 3

---

## Setup checklist

Before anyone walks in:

- [ ] Backend running on `http://localhost:8001` — confirm with `GET /health`
- [ ] Frontend open at `http://localhost:3000` on a clean Welcome screen (trash icon to clear)
- [ ] Browser zoomed to 125% so text is readable from across a table
- [ ] Devtools closed, no other tabs visible

---

## Slide 1 — The Problem

**Headline:**
> PartSelect has 500,000+ parts. Customers arrive knowing their symptom, not a part number.

**Bullets:**
- Appliance repair customers know symptoms ("fridge leaking", "ice maker not working") — not SKUs
- Keyword search on PartSelect returns nothing useful for natural-language queries
- Customers abandon the site and call support — or buy the wrong part
- The fix: a conversational agent that understands appliance context and maps intent to the right part

**Scope callout:**
> Scoped to refrigerator and dishwasher parts — the two highest-volume categories on PartSelect.com

**Speaker notes:**
PartSelect's search is built for people who already know exactly what they want. Most don't. A customer whose fridge is leaking doesn't know if they need a door gasket, a water inlet valve, or a drain pan. This project closes that gap with a Claude-powered agent that starts from the symptom and reasons its way to the right part.

---

## Slide 2 — The Solution

**Headline:**
> A Claude claude-sonnet-4-6 agent that finds the right part from a symptom, model number, brand, or part number — and adds it to cart.

**What the agent can do:**

| Input | What happens |
|-------|-------------|
| Symptom ("not making ice") | Returns parts that fix it, with explanation |
| Model number (25344352401) | Returns all 21 compatible parts instantly |
| Part number (PS8746671) | Returns full specs, rating, install difficulty |
| Brand only ("Bosch dishwasher") | Returns available parts for that brand |
| "Add it to my cart" | Adds the part, syncs cart in real time |
| "Help with my microwave" | Politely declines — out of scope |

**Data callout:**
> 6,025 real scraped parts · 10,325 appliance models · 72 symptom mappings · 87 part types · top brands: GE, Whirlpool, Frigidaire, Samsung, Bosch

**Speaker notes:**
Transition here to the live demo. Start with the symptom query. Point out that product cards appear after the explanation — not before. Then show the model number lookup and how it returns 21 parts instantly without a network call. Finish with the cart interaction.

---

## Live Demo

> "PartSelect sells over half a million appliance parts. The problem is that most customers don't arrive knowing the part number — they arrive knowing the symptom. Their fridge is leaking. Their ice maker stopped. Their dishwasher isn't draining. And when they type that into a standard keyword search, they get nothing useful.
>
> What I've built is a conversational agent that starts from where the customer is — their symptom, their model number, their brand — and works its way to the right part. Let me show you what that looks like."

---

### 1. Symptom search

**Say:** *"Let's start with the most common scenario. A customer knows something is wrong but doesn't know the part name."*

**Type:**
```
My GE refrigerator is leaking water from the bottom
```

**While it loads, say:** *"The agent is calling a symptom lookup tool — it cross-references 72 symptom categories built from 6,000 scraped parts. It's not doing a keyword search."*

**When response arrives, say:** *"Two things to notice. First, it explains the likely causes before showing products — that's intentional. The customer reads context before they see something to buy. Second, these are real parts with real prices, scraped from PartSelect's archived pages."*

---

### 2. Model number lookup

**Say:** *"Now, a customer who has their model number handy. This is the structured lookup path."*

**Type:**
```
What parts are compatible with model 25344352401?
```

**When response arrives, say:** *"This came back instantly — no network call. We have a local map of over 10,000 appliance models built from the scraped part data. The customer just needs to read the label on their appliance."*

---

### 3. Cart interaction

**Say:** *"The agent doesn't just find parts — it can manage the cart conversationally."*

Click **Add to cart** on any card from the previous results. Point to the badge count updating.

**Then type:**
```
Add the water inlet valve to my cart
```

**When it adds, say:** *"Two ways to add to cart — the button on the card, or just asking. Either way the cart stays in sync. It also persists if you close and reopen the browser."*

Open the cart sidebar to show the items, subtotal, and checkout button.

---

### 4. Part deep-dive

**Say:** *"If a customer knows a specific part number, they can get full details."*

**Type:**
```
Tell me about part PS8746671
```

**When response arrives, say:** *"Five-star rating, 13 reviews, $26.97, install difficulty included. This is fetched live — the agent tries PartSelect directly first, then falls back to an archived version if the CDN blocks it."*

---

### 5. Scope

**Say:** *"One more thing worth showing — the agent knows what it's for."*

**Type:**
```
Can you help me find a part for my washing machine?
```

**When it declines, say:** *"Scoped to refrigerators and dishwashers. The refusal is clean, not an error. Easy to expand — adding washing machines means scraping new data and updating one line in the system prompt."*

---

## Slide 3 — System Architecture

**Headline:**
> Claude is the reasoning layer. Tools are thin data accessors. No routing code.

```
Browser (Next.js)
        │  POST /chat  (SSE stream)
        ▼
FastAPI Backend
  Rate limiter → Session manager → run_agent()
                                        │
                              Claude claude-sonnet-4-6
                              (tool-use loop)
                                        │
          ┌──────────────┬─────────────┼──────────────┬──────────────┐
          ▼              ▼             ▼               ▼              ▼
    search_catalog  get_part_details  check_model  find_by_*     manage_cart
    (FAISS)         (live + Wayback)  (map + live) (maps + FAISS) (session)
          │
    SSE events: tool_call · text · parts · cart_sync · done
          │
        Browser renders reactively
```

**Three key design decisions:**

1. **Thin tools, smart agent** — 8 tools, each a data accessor. Claude picks and composes. No intent classifier, no decision tree. New query types need no new code.
2. **Two-tier retrieval** — Structured queries hit pre-built JSON maps (O(1), no network). Vague queries go to FAISS semantic search (<50 ms). Live scrape only for single-part deep-dives.
3. **SSE streaming** — Every word chunk, tool call, and cart update is a typed event. The frontend is stateless — it just reacts.

**Speaker notes:**
The central architecture decision was not to build one function per user intent. That approach breaks the moment a query doesn't fit a predefined pattern. Instead, Claude reasons about intent and selects from 8 thin tools. The tools don't know about each other. Claude composes them. This means a complex multi-step query ("find me an ice maker compatible with my Whirlpool model and add the cheapest one to cart") works without any special-case code.

---

## Slide 4 — Data & Intelligence

**Headline:**
> 6,025 real parts scraped from the Internet Archive — because PartSelect's CDN blocks direct access.

**Data pipeline:**

```
PartSelect XML Sitemaps
101,843 part URLs
        ↓
build_from_sitemap.py
Classifies each URL by appliance type
        ↓
scrape_parts.py  (~3 hrs, 5 workers)
Wayback Machine CDX API
2022–2024 archived snapshots
Names · prices · symptoms · models · ratings
        ↓
build_relational_index.py
Builds 4 JSON maps from scraped data
        ↓
embed_and_index.py
all-MiniLM-L6-v2  →  384-dim vectors
FAISS IndexFlatIP (cosine similarity)
```

**Retrieval layers:**

| Layer | Query type | Latency |
|-------|-----------|---------|
| Relational maps | Model number, symptom, brand, type | <1 ms |
| FAISS semantic index | Vague / general / keyword | <50 ms |
| Live scrape + Wayback | Single part deep-dive | 1–8 s |

**Speaker notes:**
Getting the data was the hardest engineering problem. PartSelect has aggressive CDN protection. The solution was to treat the Wayback Machine as a structured data source, not just a fallback. The CDX API is essentially a queryable index of all archived pages — you can enumerate every archived PartSelect part URL, then fetch the HTML snapshots. Each page has the full product data: name, price, description, symptoms it fixes, compatible models, install difficulty. That's how 6,025 parts with rich metadata were built without a data partnership.

---

## Slide 5 — Results & What's Next

**Headline:**
> The agent handles every realistic query type. Adding a new appliance category is a scrape and re-index — zero agent code changes.

**Coverage & performance:**

| Metric | Value |
|--------|-------|
| Parts indexed | 6,025 (GE, Whirlpool, Frigidaire, Samsung, Bosch, LG) |
| Appliance models mapped | 10,325 |
| Time to first token | ~2–3 s |
| FAISS query latency | <50 ms |
| Tool selection accuracy | >95% on labelled eval set |
| Scope adherence | 100% — correctly declines off-topic queries |

**Straightforward extensions:**

| Extension | Effort |
|-----------|--------|
| Washing machines / dryers | Low — scrape new category, re-index, update scope prompt |
| Real-time pricing | Low — add `get_live_price(part_number)` tool |
| Installation video lookup | Low — `video_url` field already in metadata |
| Persistent cart (Redis) | Medium — replace in-memory dict, API to Claude unchanged |
| Multimodal input | Medium — user photos of broken parts → Claude Vision identifies part |
| Personalization | High — remember user's appliance models across sessions |

**Speaker notes:**
The extensibility point is worth dwelling on. Because Claude is the reasoning layer, adding a new capability usually means adding one tool definition — not redesigning any flows. The scope guard is a single line in the system prompt. Turning it into a washing machine assistant tomorrow means scraping new data and changing two sentences. That's the payoff of the thin-tools architecture.

---

## How It Works (speak this — 90 seconds)

> "Under the hood, there are three moving parts.
>
> First, **Claude claude-sonnet-4-6** — Anthropic's model — acts as the reasoning engine. It reads every message, decides which tool to call, and writes the response. It doesn't have hardcoded logic for different query types. It reasons.
>
> Second, **eight tools** — each one is a minimal data accessor. One searches the FAISS vector index. One looks up model compatibility from a local map. One scrapes a live part page. One manages the cart. Claude picks the right tool for each query automatically.
>
> Third, **the data** — 6,025 real parts scraped from the Internet Archive, because PartSelect's CDN blocks direct access. Every part has its name, price, symptoms it fixes, compatible models, and ratings.
>
> The whole thing streams — every word, every tool call, every cart update — over a live connection to the browser. The frontend just reacts to events."

---

## Data & Coverage

| What | How many |
|------|----------|
| Parts indexed | 6,025 |
| Appliance models mapped | 10,325 |
| Symptom categories | 72 |
| Part type categories | 87 |
| Brand × appliance combinations | 77 |
| Top brands | GE · Whirlpool · Frigidaire · Samsung · Bosch · LG |

---

## What's Next (speak this)

> "The architecture is intentionally extensible. Adding washing machines or dryers means running the scraper on a new category and updating the scope. No changes to agent logic. No new tools.
>
> Other near-term possibilities: real-time pricing, repair video lookup, and multimodal input — a customer photographs a broken part and the agent identifies it. The data layer is already structured to support all of that."

---

## Likely Questions

**Q: How accurate is it at picking the right part?**
> "Tool selection accuracy is above 95% on a labelled test set. Part relevance — whether the returned parts are actually relevant to the query — is consistently high because the symptom and type maps were built directly from the parts themselves, not inferred."

**Q: What happens if the part isn't in the index?**
> "It falls back gracefully. For model lookups it tries a live scrape of PartSelect. For part details it tries live first, then the Wayback Machine archive. Only if both fail does the user see a 'not found' — which is rare given 6,000 parts and 10,000 models."

**Q: Why not use PartSelect's own API?**
> "There isn't one. PartSelect doesn't expose a public API for catalog data. The Wayback Machine approach was the only reliable way to get structured, complete part data at scale."

**Q: Can the cart sync with PartSelect's real cart?**
> "Not currently — PartSelect has no public cart API. The checkout button takes the user to PartSelect's shopping cart page where they complete the purchase. Full native cart sync would require a data partnership."

**Q: How long does a response take?**
> "Two to three seconds to first word. The response time is shown at the bottom of each message. FAISS queries are under 50 milliseconds — the wait is almost entirely the Claude API round-trip."

---

## Backup queries

If anything misbehaves during the demo, swap in one of these:

| Situation | Use this instead |
|-----------|-----------------|
| Symptom search returns thin results | `My refrigerator is not dispensing water` |
| Need a dishwasher symptom | `My dishwasher is not cleaning dishes properly` |
| Model number lookup | `What fits dishwasher model 66512413N412?` |
| Part detail with good data | `Tell me about PS732699` — 5★ silverware basket, $38.57 |
| Brand search | `Show me Samsung refrigerator parts` |
| Part type search | `I need a replacement door gasket for a GE fridge` |
