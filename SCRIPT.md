# PartSelect Agent — Speaker Script

---

## Opening

PartSelect sells over half a million appliance parts. The problem is that most customers don't arrive knowing the part number — they arrive knowing the symptom. Their fridge is leaking. Their ice maker stopped. Their dishwasher isn't draining. And when they type that into a standard keyword search, they get nothing useful.

What I've built is a conversational agent that starts from where the customer is — their symptom, their model number, their brand — and works its way to the right part.

---

## Slide 1 — The Problem

PartSelect's search is built for people who already know exactly what they want. Most don't.

A customer whose fridge is leaking doesn't know if they need a door gasket, a water inlet valve, or a drain pan. They just know something is wrong. Keyword search returns nothing for that. They abandon the site, call support, or buy the wrong part.

The fix is a conversational agent that understands appliance context and maps intent to the right part. I've scoped it to refrigerators and dishwashers — the two highest-volume categories on PartSelect.

---

## Slide 2 — The Solution

The agent is powered by Claude — Anthropic's model. You can give it a symptom, a model number, a part number, or just a brand, and it finds the right part. You can also just say "add it to my cart" and it does.

It also knows what it's not for. Ask it about a washing machine and it declines cleanly — it doesn't error, it just tells you it's scoped to fridges and dishwashers. That scope is easy to expand.

Let me show you what this actually looks like.

---

## Live Demo

*(Switch to browser.)*

**Query 1 — Symptom search**

I'll start with the most common scenario. A customer knows something is wrong but doesn't know the part name.

*(Type: My GE refrigerator is leaking water from the bottom)*

The agent is calling a symptom lookup tool — it cross-references 72 symptom categories built from 6,000 scraped parts. It's not doing a keyword match.

Two things to notice in the response. First, it explains the likely causes before showing products — that's intentional. The customer understands the problem before they see something to buy. Second, these are real parts with real prices, pulled from PartSelect's archived pages.

---

**Query 2 — Model number lookup**

Now a customer who has their model number. This is the fast path.

*(Type: What parts are compatible with model 25344352401?)*

That came back instantly — no network call. We have a local map of over 10,000 appliance models built from the scraped data. The customer just reads the label on their appliance and gets every compatible part in under a second.

---

**Query 3 — Cart**

The agent doesn't just find parts — it manages the cart conversationally.

*(Click Add to cart on a result card. Point to the badge.)*

You can also just ask.

*(Type: Add the water inlet valve to my cart)*

Two ways to add — the button or just asking. Either way the cart stays in sync. It also persists across browser refreshes.

*(Open the cart sidebar.)*

Items, subtotal, checkout button that takes you straight to PartSelect.

---

**Query 4 — Part detail**

If a customer knows a specific part number, they can get the full picture.

*(Type: Tell me about part PS8746671)*

Five-star rating, 13 reviews, $26.97, install difficulty included. This is fetched live — the agent tries PartSelect directly first, then falls back to an archived version if the CDN blocks it.

---

**Query 5 — Scope**

One more thing worth showing.

*(Type: Can you help me find a part for my washing machine?)*

Clean decline. Not an error. Adding washing machines means scraping new data and changing one line in the system prompt — no agent logic changes.

---

## Slide 3 — Architecture

Under the hood, there are three moving parts.

First, Claude acts as the reasoning engine. It reads every message, decides which tool to call, and writes the response. There's no hardcoded routing, no intent classifier, no decision tree. It just reasons.

Second, eight tools — each one is a minimal data accessor. One searches the FAISS vector index. One looks up model compatibility from a local map. One scrapes a live part page. One manages the cart. Claude picks the right tool automatically, and composes them when a query needs more than one.

Third, everything streams. Every word, every tool call, every cart update goes over a live server-sent event connection to the browser. The frontend is stateless — it just reacts to events.

The retrieval is two-tier. Structured queries — model numbers, symptom categories, brands — hit pre-built JSON maps. That's under a millisecond, no network. Vague or open-ended queries go to FAISS semantic search, which is under 50 milliseconds. A live scrape only happens when someone asks for a specific part's full details.

---

## Slide 4 — Data

Getting the data was the hardest engineering problem.

PartSelect has aggressive CDN protection — direct scraping is blocked. The solution was the Internet Archive's Wayback Machine. Their CDX API lets you enumerate every archived PartSelect part URL, and then fetch HTML snapshots from 2022 to 2024. Each snapshot has the full product data: name, price, description, symptoms it fixes, compatible models, install difficulty.

That's how I built 6,025 parts with rich metadata without a data partnership.

From the raw HTML I built four relational maps — symptom to parts, part type to parts, model to parts, brand to parts. Then I embedded every part name and description into a 384-dimensional vector space using a sentence transformer model, and indexed those in FAISS for semantic search.

The whole pipeline runs locally. No OpenAI, no external vector database, no API keys.

---

## Slide 5 — Results & What's Next

The agent handles every realistic query type. Tool selection accuracy is above 95% on a labelled test set. Scope adherence is 100% — it correctly declines every out-of-scope query. Time to first word is two to three seconds, which is almost entirely the Claude API round-trip. FAISS queries are under 50 milliseconds.

The architecture is intentionally extensible. Adding washing machines or dryers means running the scraper on a new category and updating the scope. No changes to agent logic. No new tools.

Other near-term directions: real-time pricing, installation video lookup — the metadata field is already there — and multimodal input, where a customer photographs a broken part and the agent identifies it. The data layer is already structured to support all of that.

---

## Q&A

**How accurate is it at picking the right part?**

Tool selection accuracy is above 95% on a labelled test set. Part relevance is consistently high because the symptom and type maps were built directly from the parts themselves, not inferred from general text.

**What happens if the part isn't in the index?**

It falls back gracefully. For model lookups it tries a live scrape of PartSelect. For part details it tries live first, then the Wayback Machine. Only if both fail does the user see a not-found — which is rare given 6,000 parts and 10,000 models.

**Why not use PartSelect's own API?**

There isn't one. PartSelect doesn't expose a public API for catalog data. The Wayback Machine was the only reliable way to get structured, complete part data at scale.

**Can the cart sync with PartSelect's real cart?**

Not currently — PartSelect has no public cart API. The checkout button takes the user to PartSelect's cart page where they complete the purchase. Full native sync would require a data partnership.

**How long does a response take?**

Two to three seconds to first word. The response time is shown at the bottom of each message. FAISS queries are under 50 milliseconds — the wait is almost entirely the Claude API round-trip.
