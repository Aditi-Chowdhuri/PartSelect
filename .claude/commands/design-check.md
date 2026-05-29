Audit the frontend for design violations. Read all component files in frontend/src/components/ and check:

1. Color usage — only gray-900 and brand-orange (#e8651a) should appear in product UI. Flag any text-brand-blue, text-blue-*, bg-blue-* in product-facing components.
2. No emojis in any component output.
3. CartSidebar — price should use text-gray-900, links should use text-gray-400 hover:text-brand-orange.
4. PartCard — part number and price display, add-to-cart button uses brand-orange.
5. WelcomeScreen — suggestion queries must use verified model numbers and part numbers that exist in the index.
6. ChatInterface — error messages display correctly, streaming text renders progressively.
7. Responsive layout — max-w-xl or max-w-2xl containers, px-4 padding.

Report every violation with the file path, line number, and the fix.
