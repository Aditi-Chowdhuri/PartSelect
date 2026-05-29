Start the frontend development server locally. From the frontend/ directory:

1. Check that .env.local exists and contains NEXT_PUBLIC_BACKEND_URL=http://localhost:8001. If missing, create it from .env.local.example.
2. Check that node_modules/ exists. If not, run npm install first.
3. Run: npm run dev
4. Confirm the server starts at http://localhost:3000.
5. Remind the user the backend must also be running on port 8001 for chat to work.
