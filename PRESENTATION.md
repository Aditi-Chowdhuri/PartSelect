# PartSelect Chat Agent — 5-Slide Presentation

---

## Slide 1 — The Problem

**Headline:**
> PartSelect has 500,000+ parts. Customers arrive knowing their symptom, not a part number.

**Visual:** Split screen — left: a frustrated user typing "ice maker not working" into a standard keyword search bar getting zero results. Right: the same query in the chat agent returning relevant parts with an explanation.

**Bullets:**
- Appliance repair customers know symptoms ("fridge leaking", "ice maker not working") — not SKUs
- Keyword search on PartSelect returns nothing useful for natural-language queries
- Customers abandon the site and call support — or buy the wrong part
- The fix: a conversational agent that understands appliance context and maps intent to the right part

**Scope callout (bottom of slide):**
> Scoped to refrigerator and dishwasher parts — the two highest-volume categories on PartSelect.com

**Speaker notes:**
PartSelect's search is built for people who already know exactly what they want. Most don't. A customer whose fridge is leaking doesn't know if they need a door gasket, a water inlet valve, or a drain pan. This project closes that gap with a Claude-powered agent that starts from the symptom and reasons its way to the right part.

---

## Slide 2 — The Solution

**Headline:**
> A Claude claude-sonnet-4-6 agent that finds the right part from a symptom, model number, brand, or part number — and adds it to cart.

**Visual:** Screenshot of the UI showing a chat response to "My GE refrigerator is leaking water from the bottom" — streaming text explanation followed by product cards.

**What the agent can do (two columns):**

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
Show the live demo here. Start with the symptom query. Point out that product cards appear after the explanation — not before. Then show the model number lookup and how it returns 21 parts instantly without a network call. Finish with the cart interaction — Claude calling manage_cart and the badge updating in real time.

---

## Slide 3 — System Architecture

**Headline:**
> Claude is the reasoning layer. Tools are thin data accessors. No routing code.

**Visual:** The system architecture diagram (`System Design.png`) — or the ASCII diagram below reproduced cleanly.

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

**Three key design decisions on this slide:**

1. **Thin tools, smart agent** — 8 tools, each a data accessor. Claude picks and composes. No intent classifier, no decision tree. New query types need no new code.
2. **Two-tier retrieval** — Structured queries hit pre-built JSON maps (O(1), no network). Vague queries go to FAISS semantic search (<50 ms). Live scrape only for single-part deep-dives.
3. **SSE streaming** — Every word chunk, tool call, and cart update is a typed event. The frontend is stateless — it just reacts.

**Speaker notes:**
The central architecture decision was not to build one function per user intent. That approach breaks the moment a query doesn't fit a predefined pattern. Instead, Claude reasons about intent and selects from 8 thin tools. The tools don't know about each other. Claude composes them. This means a complex multi-step query ("find me an ice maker compatible with my Whirlpool model and add the cheapest one to cart") works without any special-case code.

---

## Slide 4 — Data & Intelligence

**Headline:**
> 6,025 real parts scraped from the Internet Archive — because PartSelect's CDN blocks direct access.

**Visual:** Two-column layout. Left: the data pipeline flow. Right: the retrieval layer diagram.

**Data pipeline (left column):**

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

**Retrieval layers (right column):**

| Layer | Query type | Latency |
|-------|-----------|---------|
| Relational maps | Model number, symptom, brand, type | <1 ms |
| FAISS semantic index | Vague / general / keyword | <50 ms |
| Live scrape + Wayback | Single part deep-dive | 1–8 s |

**Why Wayback Machine:**
PartSelect's CDN (Akamai) blocks automated access. The Internet Archive's CDX API enumerates all archived pages and provides 2022–2024 HTML snapshots with complete metadata. The same Wayback proxy is used at runtime to serve part images.

**Speaker notes:**
Getting the data was the hardest engineering problem. PartSelect has aggressive CDN protection. The solution was to treat the Wayback Machine as a structured data source, not just a fallback. The CDX API is essentially a queryable index of all archived pages — you can enumerate every archived PartSelect part URL, then fetch the HTML snapshots. Each page has the full product data: name, price, description, symptoms it fixes, compatible models, install difficulty. That's how 6,025 parts with rich metadata were built without a data partnership.

---

## Slide 5 — Results & What's Next

**Headline:**
> The agent handles every realistic query type. Adding a new appliance category is a scrape and re-index — zero agent code changes.

**Visual:** UI screenshot showing the cart with items, or the welcome screen with the suggestion chips. Alternatively use the `UI Design Spec.png`.

**Coverage & performance:**

| Metric | Value |
|--------|-------|
| Parts indexed | 6,025 (GE, Whirlpool, Frigidaire, Samsung, Bosch, LG) |
| Appliance models mapped | 10,325 |
| Time to first token | ~2–3 s |
| FAISS query latency | <50 ms |
| Tool selection accuracy | >95% on labelled eval set |
| Scope adherence | 100% — correctly declines off-topic queries |

**What works today:**
- Symptom → parts (72 symptom mappings)
- Model compatibility (10,325 models)
- Part deep-dive with live + archived data
- Brand and type browsing
- Conversational cart management
- Session persistence, rate limiting, CORS, localStorage cart

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
The extensibility point is worth dwelling on. Because Claude is the reasoning layer, adding a new capability usually means adding one tool definition and one dispatch case — not redesigning any flows. The scope guard is a single line in the system prompt. Turning it into a washing machine assistant tomorrow means scraping new data and changing two sentences. That's the payoff of the thin-tools architecture.

---

## Presentation notes

- **Total time:** 10–12 minutes (2 min/slide) + 3 min live demo between slides 2 and 3
- **Demo order:** Run Scene 2 (symptom search) → Scene 3 (model compatibility) → Scene 4 (add to cart) from DEMO.md
- **Slide order:** Problem → Solution + demo → Architecture → Data → Results
- **Handout:** Share the GitHub repo link; DEMO.md has all backup queries and talking points
