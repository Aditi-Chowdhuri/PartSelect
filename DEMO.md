# PartSelect Chat Agent — Demo Script

**Runtime:** ~6 minutes  
**Setup:** Backend on `http://localhost:8001`, frontend on `http://localhost:3000`

---

## Before you start

- Clear the chat (trash icon, top right) so you open on the Welcome screen
- Have the browser devtools closed — keep the UI clean
- The first query of the session triggers FAISS + model loading (~2 s cold start); subsequent queries are fast

---

## Scene 1 — The problem (30 s)

> "PartSelect has over half a million appliance parts. Most customers arrive knowing their symptom — 'my fridge is leaking' — not a part number. Keyword search fails them completely. This agent understands the problem and maps it directly to the right part."

Point to the Welcome screen. Show the three tabs (All / Refrigerator / Dishwasher). Don't click anything yet.

---

## Scene 2 — Symptom search (90 s)

**Type this exactly:**
```
My GE refrigerator is leaking water from the bottom
```

**What happens:**
1. Status label: *"Finding parts for that symptom…"*
2. Streaming text response explains common causes (door seal, water inlet valve, drain pan)
3. Product cards appear **after** the text — 5–8 parts, each with name, part number, brand, price
4. All parts are real GE refrigerator parts from the scraped index

**Talk through:**
- "The agent picked `find_parts_by_symptom` — a structured lookup against 72 symptom keys built from 6,000 scraped parts, not a keyword search"
- "Cards appear after the explanation — the user always reads context before seeing something to buy"
- "These are real prices and part numbers from archived PartSelect pages"

---

## Scene 3 — Model compatibility (60 s)

**Type this exactly:**
```
What parts are compatible with model 25344352401?
```

**What happens:**
1. Status label: *"Checking model compatibility…"*
2. Claude identifies this as a Kenmore refrigerator
3. Returns up to 21 compatible parts from the local relational map (instant — no network call)

**Talk through:**
- "Model number → `check_model_compatibility` — hits a local map of 10,325 appliance models built from the scraped compatible-models field on each part page"
- "Zero network latency — the answer comes from a pre-built JSON map loaded at startup"
- "A customer just needs to type their model number off the label"

---

## Scene 4 — Add to cart (45 s)

Click **Add to cart** on any part card from Scene 2 or 3.

**What happens:**
1. Cart badge in the header immediately shows **1**
2. Click the cart icon — drawer slides in showing the item, quantity controls, subtotal
3. The cart is also synced on the server side via a `cart_sync` SSE event

**Then ask Claude to add something:**
```
Add that water inlet valve to my cart
```

**What happens:**
1. Status label: *"Updating cart…"*
2. Claude calls `manage_cart` → server updates → `cart_sync` event fires → cart badge updates in real time
3. Claude confirms the addition in text

**Talk through:**
- "Two paths to cart: the UI button (client-only) and asking Claude directly (server-synced). Either way the cart stays consistent"
- "Cart persists across page refreshes via localStorage — close and reopen the tab to show it"

---

## Scene 5 — Part deep-dive (45 s)

**Type this exactly:**
```
Tell me about part PS8746671
```

**What happens:**
1. Status label: *"Fetching part details…"*
2. Agent tries live PartSelect first, falls back to Wayback Machine archive
3. Returns: name (Lower Spray Arm), price ($26.97), 5.0★ rating, 13 reviews, installation info

**Talk through:**
- "Part number → `get_part_details` — live scrape of PartSelect with Wayback Machine as fallback. PartSelect's CDN blocks automated access, so the agent uses the Internet Archive"
- "This is real data: $26.97, 5 stars, 13 reviews"

---

## Scene 6 — Brand search (30 s)

**Type this exactly:**
```
Show me Bosch dishwasher parts
```

**What happens:**
1. Status label: *"Looking up brand parts…"*
2. Returns 8 Bosch dishwasher parts from the brand × appliance relational map

**Talk through:**
- "Brand-only query → `find_parts_by_brand` — a separate map that groups parts by brand and appliance type"
- "Same tool-selection logic handles every query type without any routing code — Claude reasons about intent and picks the right tool"

---

## Scene 7 — Scope guard (15 s)

**Type this exactly:**
```
Can you help me find a part for my microwave?
```

**What happens:**
Claude declines cleanly:
> "I'm specialized in refrigerator and dishwasher parts — I'm not able to help with microwave parts, but I'd be happy to help you find the right part for your appliance!"

**Talk through:**
- "The agent is scoped to refrigerators and dishwashers. The system prompt enforces this — no special routing code, just a rule Claude follows"

---

## Backup queries

If any scene doesn't produce good results, use these alternatives:

| Intent | Backup query |
|--------|-------------|
| Symptom (fridge) | `My refrigerator is not dispensing water` |
| Symptom (dishwasher) | `My dishwasher is not cleaning dishes properly` |
| Model number | `What fits dishwasher model 66512413N412?` |
| Part detail | `What can you tell me about PS732699?` (5★ silverware basket, $38.57) |
| Brand | `I have a Samsung refrigerator, what parts do you carry?` |
| Part type | `I need a replacement door gasket for a GE refrigerator` |

---

## Key talking points (to weave in throughout)

| Point | When to say it |
|-------|---------------|
| **6,025 real parts** scraped from PartSelect via Wayback Machine CDX | Scene 2 |
| **8 tools, thin data accessors** — Claude is the reasoning layer, not a decision tree | Any tool call |
| **SSE streaming** — each word chunk, tool call, and cart update is a typed event; frontend is purely reactive | Scene 4 |
| **Zero external vector DB** — FAISS runs locally, 384-dim all-MiniLM-L6-v2 embeddings, <50 ms per query | Scene 2 or 5 |
| **Parts buffer** — product cards are held until the first text token so context always precedes purchase options | Scene 2 |
| **New appliance category = scrape + re-index** — zero changes to agent code | Wrap-up |

---

## Architecture in one sentence

> Claude picks the right tool, the tools return structured data, and SSE streams everything — text, parts, and cart state — to a stateless React frontend.
