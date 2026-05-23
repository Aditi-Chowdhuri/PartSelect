# PartSelect Chat Agent — Client Standup

---

## Setup checklist

Before anyone walks in:

- [ ] Backend running on `http://localhost:8001` — confirm with `GET /health`
- [ ] Frontend open at `http://localhost:3000` on a clean Welcome screen (trash icon to clear)
- [ ] Browser zoomed to 125% so text is readable from across a table
- [ ] Devtools closed, no other tabs visible

---

## Opening (speak this)

> "PartSelect sells over half a million appliance parts. The problem is that most customers don't arrive knowing the part number — they arrive knowing the symptom. Their fridge is leaking. Their ice maker stopped. Their dishwasher isn't draining. And when they type that into a standard keyword search, they get nothing useful.
>
> What I've built is a conversational agent that starts from where the customer is — their symptom, their model number, their brand — and works its way to the right part. Let me show you what that looks like."

---

## Live Demo

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

If asked, have these numbers ready:

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

If anything misbehaves, swap in one of these:

| Situation | Use this instead |
|-----------|-----------------|
| Symptom search returns thin results | `My refrigerator is not dispensing water` |
| Need a dishwasher symptom | `My dishwasher is not cleaning dishes properly` |
| Model number lookup | `What fits dishwasher model 66512413N412?` |
| Part detail with good data | `Tell me about PS732699` — 5★ silverware basket, $38.57 |
| Brand search | `Show me Samsung refrigerator parts` |
| Part type search | `I need a replacement door gasket for a GE fridge` |
