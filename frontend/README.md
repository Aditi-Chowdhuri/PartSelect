# PartSelect Frontend

Next.js 14 (App Router) chat interface that streams responses from the backend agent.

---

## Setup

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev     # http://localhost:3000
```

For production:

```bash
npm run build
npm start
```

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | Yes | `http://localhost:8001` | Backend API base URL |

---

## Components

| Component | File | Responsibility |
|-----------|------|----------------|
| Page root | `src/app/page.tsx` | Chat state, SSE stream handling, cart state, parts buffer |
| Message display | `src/components/MessageBubble.tsx` | Renders user/assistant turns, inline markdown, product card rows, tool status labels |
| Product card | `src/components/ProductCard.tsx` | Part name, number, brand, rating, price, Add-to-cart and View buttons |
| Cart sidebar | `src/components/CartSidebar.tsx` | Sliding drawer with quantity controls, subtotal, and checkout link |
| Welcome screen | `src/components/WelcomeScreen.tsx` | Greeting, appliance filter tabs, suggestion prompts |
| Error boundary | `src/components/ErrorBoundary.tsx` | Catches render errors, shows retry button |
| API client | `src/lib/api.ts` | `streamChat()` async generator — parses SSE events, surfaces 429 Retry-After |

---

## SSE event handling

The backend streams typed SSE events. The frontend handles them as follows:

| Event | Action |
|-------|--------|
| `tool_call` | Show status label in the current message ("Searching catalog…") |
| `text` | Append word chunk to assistant message; on first chunk, flush any buffered parts |
| `parts` | Hold in `partsBuffer` until first text chunk arrives, then attach to message |
| `cart_sync` | Replace `cartItems` state atomically with server's authoritative cart |
| `done` | Record response time, show follow-up suggestion chips |

**Parts buffer:** product cards are held until the first text token arrives so the user always reads context before seeing purchase options.

---

## Cart persistence

Cart state is kept in two places simultaneously:

| Store | Scope | Purpose |
|-------|-------|---------|
| React state (`cartItems`) | Session | Drives all UI rendering |
| `localStorage` (`partselect_cart`) | Browser | Survives page refresh |
| Backend `_carts` dict | Server session | Authoritative when Claude manages cart via `manage_cart` tool |

On page load, cart state is seeded from `localStorage`. When the backend emits a `cart_sync` event (after any `manage_cart` tool call), React state and `localStorage` are both updated from the server's version.

---

## Design decisions

- **No chat bubbles for the assistant.** Text flows on white to match Claude.ai's aesthetic. User messages use a gray pill.
- **Cards after text, always.** The parts buffer ensures product cards never render before the explanation.
- **Single accent color.** Gray-900 for UI chrome, `#e8651a` (brand orange) for the CTA (Add to cart, cart badge, checkout). No blue in the product flow.
- **No part images.** PartSelect's CDN blocks hotlinking and Wayback proxying adds latency. Cards are text-only: name, part number, brand, rating, price.
