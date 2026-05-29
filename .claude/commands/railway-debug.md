Debug a Railway deployment failure for this project. Check the following in order:

1. Confirm railway.toml exists at the repo root (not inside backend/) and has builder = "DOCKERFILE" and dockerfilePath = "backend/Dockerfile".
2. Read backend/Dockerfile and confirm: COPY paths are relative to the backend/ build context (i.e. COPY requirements.txt . not COPY backend/requirements.txt .), the CMD uses ${PORT:-8000} not a hardcoded port, and the sentence-transformers model is pre-downloaded at build time.
3. Confirm backend/.dockerignore exists and excludes .env and __pycache__.
4. Check Railway service Settings: Root Directory should be set to backend, Builder should be Dockerfile.
5. Remind the user that ANTHROPIC_API_KEY and ALLOWED_ORIGINS must be set in Railway Variables.

Report exactly what is misconfigured.
