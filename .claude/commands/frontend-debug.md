Debug a frontend issue. Read the following files and identify the problem:

1. frontend/src/lib/api.ts — check BACKEND_URL construction, SSE event handling, error handling
2. frontend/src/components/ChatInterface.tsx — check message state, streaming logic, error display
3. frontend/src/components/WelcomeScreen.tsx — check suggestion queries, filter tabs
4. frontend/src/components/CartSidebar.tsx — check cart state, localStorage persistence
5. frontend/src/components/PartCard.tsx — check part rendering, add-to-cart handler
6. frontend/.env.local — check NEXT_PUBLIC_BACKEND_URL value

Common issues:
- NEXT_PUBLIC_BACKEND_URL has a trailing slash (causes //chat double-slash 404)
- NEXT_PUBLIC_BACKEND_URL points to localhost in production (must be the Railway URL)
- SSE stream not handled (missing event type in the switch)
- Cart not persisting (localStorage key mismatch)
- Design violations (text-brand-blue instead of text-gray-900 or text-brand-orange)

Report the likely cause and exact fix.
