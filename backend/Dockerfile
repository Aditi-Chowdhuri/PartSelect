FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embedding model so cold starts don't block on a 90 MB download
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY backend/ .

EXPOSE 8000

# Railway injects $PORT at runtime; fall back to 8000 for local docker run
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
