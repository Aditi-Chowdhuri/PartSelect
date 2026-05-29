Check the health of the live deployment. Do the following:
1. Confirm the latest commit on origin/main matches what was last pushed.
2. Remind the user to check Railway deploy logs at partselect-production.up.railway.app and confirm the service is Active and /health returns 200 OK.
3. Remind the user to confirm https://part-select.vercel.app loads the frontend correctly.
4. List the two Railway environment variables required: ANTHROPIC_API_KEY and ALLOWED_ORIGINS=https://part-select.vercel.app
5. List the one Vercel environment variable required: NEXT_PUBLIC_BACKEND_URL=https://partselect-production.up.railway.app (no trailing slash).
Report any mismatches or missing items.
