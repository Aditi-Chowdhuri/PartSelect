Diagnose and fix a CORS or "Failed to fetch" error between the Vercel frontend and the Railway backend.

Check the following in order:
1. Read backend/app/main.py to find how ALLOWED_ORIGINS is parsed.
2. Confirm ALLOWED_ORIGINS in Railway Variables matches the exact Vercel origin — no trailing slash, comma-separated if multiple origins.
3. Confirm NEXT_PUBLIC_BACKEND_URL in Vercel Environment Variables is set to https://partselect-production.up.railway.app with no trailing slash.
4. Confirm NEXT_PUBLIC_BACKEND_URL is set for All Environments (Production + Preview), not just Production.
5. If NEXT_PUBLIC_BACKEND_URL was changed, remind the user that a Vercel redeploy is required (it is baked in at build time).

Report exactly what is wrong and what to fix.
