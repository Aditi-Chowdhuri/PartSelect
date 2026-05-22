import os
import re
import time
import uuid
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
import httpx

from .models import ChatRequest
from .claude_client import run_agent
from .tools import manage_cart

load_dotenv(Path(__file__).parent.parent / ".env")

_STEALTH = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.partselect.com/",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}
_CDN = "partselectcom-gtcdcddbene3cpes.z01.azurefd.net"
_img_cache: dict[str, tuple[bytes, str]] = {}  # pn -> (content, content-type)

# ── Rate limiting ─────────────────────────────────────────────────────────────
_RATE_LIMIT = 20        # max requests per 60-second sliding window
_RATE_WINDOW = 60.0
_rate_data: dict[str, list[float]] = {}

# ── Session TTL ───────────────────────────────────────────────────────────────
_SESSION_TTL = 7200.0   # 2 hours
_session_last_seen: dict[str, float] = {}


# ── Background cleanup ────────────────────────────────────────────────────────

async def _cleanup_loop():
    """Every 5 minutes: evict stale carts and expired rate-limit buckets."""
    while True:
        await asyncio.sleep(300)
        now = time.monotonic()

        stale_sessions = [sid for sid, ts in _session_last_seen.items() if now - ts > _SESSION_TTL]
        if stale_sessions:
            from .tools import _carts
            for sid in stale_sessions:
                _carts.pop(sid, None)
                _session_last_seen.pop(sid, None)

        stale_ips = [ip for ip, tss in _rate_data.items() if not tss or now - tss[-1] > _RATE_WINDOW]
        for ip in stale_ips:
            _rate_data.pop(ip, None)


# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()


app = FastAPI(title="PartSelect Chat Agent", lifespan=lifespan)

_cors_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> bool:
    now = time.monotonic()
    _rate_data[ip] = [t for t in _rate_data.get(ip, []) if now - t < _RATE_WINDOW]
    if len(_rate_data[ip]) >= _RATE_LIMIT:
        return False
    _rate_data[ip].append(now)
    return True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/image/{part_number}")
async def part_image(part_number: str):
    """
    Proxy endpoint: fetches part images from Wayback Machine CDX.
    PartSelect's CDN blocks all hotlinking; Wayback serves cached copies.
    Results are held in a process-level dict so repeated loads are instant.
    """
    pn = re.sub(r"[^0-9]", "", part_number)
    if not pn:
        raise HTTPException(status_code=400, detail="Invalid part number")

    cached = _img_cache.get(pn)
    if cached:
        return Response(content=cached[0], media_type=cached[1])

    async with httpx.AsyncClient(headers=_STEALTH, follow_redirects=True, timeout=20) as client:
        # CDX: find cached images for this part number
        try:
            cdx = await client.get(
                "https://web.archive.org/cdx/search/cdx",
                params={
                    "url":      f"{_CDN}/{pn}*",
                    "output":   "json",
                    "fl":       "timestamp,original",
                    "filter":   "statuscode:200",
                    "limit":    10,
                    "collapse": "original",
                },
                timeout=10,
            )
            rows = cdx.json()   # raises JSONDecodeError if CDX returns non-JSON
        except json.JSONDecodeError:
            # CDX returned HTML (maintenance page) — treat as not found, not server error
            raise HTTPException(status_code=404, detail=f"Image unavailable for PS{pn}")
        except Exception:
            raise HTTPException(status_code=404, detail=f"Image unavailable for PS{pn}")

        if len(rows) < 2:
            raise HTTPException(status_code=404, detail=f"No image found for PS{pn}")

        candidates = rows[1:]
        candidates.sort(key=lambda r: (1 if r[1].lower().endswith((".jpg", ".jpeg")) else 0), reverse=True)

        for ts, orig in candidates[:6]:
            wb_url = f"https://web.archive.org/web/{ts}im_/{orig}"
            try:
                r = await client.get(wb_url, timeout=15)
                ct = r.headers.get("content-type", "")
                if r.status_code == 200 and "image" in ct and len(r.content) > 800:
                    _img_cache[pn] = (r.content, ct)
                    return Response(content=r.content, media_type=ct)
            except Exception:
                continue

    raise HTTPException(status_code=404, detail=f"Image unavailable for PS{pn}")


@app.post("/chat")
async def chat(request: Request, body: ChatRequest):
    ip = _client_ip(request)
    if not _check_rate_limit(ip):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please wait before trying again."},
            headers={"Retry-After": str(int(_RATE_WINDOW))},
        )

    if len(body.messages) > 100:
        raise HTTPException(status_code=400, detail="Message history too long.")

    session_id = body.session_id or str(uuid.uuid4())
    _session_last_seen[session_id] = time.monotonic()

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    return StreamingResponse(
        run_agent(messages, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.delete("/cart/{session_id}")
async def clear_cart(session_id: str):
    manage_cart(session_id=session_id, action="view")
    from .tools import _carts
    _carts.pop(session_id, None)
    _session_last_seen.pop(session_id, None)
    return {"status": "cleared", "session_id": session_id}
