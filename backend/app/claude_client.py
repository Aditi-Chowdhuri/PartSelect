import asyncio
import json
import os
import re
from typing import AsyncGenerator
import anthropic

from .tools import (
    TOOL_DEFINITIONS,
    search_catalog,
    get_part_details,
    check_model_compatibility,
    manage_cart,
    get_order,
)

SYSTEM_PROMPT = """You are a helpful assistant for PartSelect.com, specializing exclusively in refrigerator and dishwasher parts.

You help customers:
- Find the right parts by symptom, model number, or part number
- Check compatibility between parts and appliance models
- Understand how to install parts and troubleshoot appliance issues
- Manage their cart and check order status

IMPORTANT RULES:
1. Only answer questions about refrigerator and dishwasher parts available on PartSelect.com. Politely decline everything else.
2. Always use your tools before answering product questions — never make up part numbers, prices, or compatibility info.
3. When a user mentions a model number (e.g. WDT780SAEM1), call check_model_compatibility.
4. When a user mentions a part number (e.g. PS11752778), call get_part_details.
5. When asked about symptoms or broken appliances, call search_catalog with descriptive query terms.
6. Always cite PartSelect.com as your source.
7. Be concise, friendly, and technically accurate.

For off-topic questions, respond: "I'm specialized in refrigerator and dishwasher parts — I'm not able to help with [topic], but I'd love to help you find the right part for your appliance!"
"""

# ── Part normalisation ────────────────────────────────────────────────────────

def _safe_price(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.replace("$", "").replace(",", "").strip())
        except ValueError:
            return 0.0
    return 0.0


def _normalise_part(p: dict) -> dict:
    """Produce a consistent Part shape for the frontend."""
    return {
        "part_number":       p.get("part_number", ""),
        "name":              p.get("name", ""),
        "price":             _safe_price(p.get("price", 0)),
        "brand":             p.get("brand", ""),
        "category":          p.get("category", ""),
        "image_url":         p.get("image_url", ""),
        "description":       p.get("description", "")[:300],
        "url":               p.get("url", ""),
        "rating":            float(p.get("rating") or 0),
        "review_count":      int(p.get("review_count") or 0),
        "availability":      p.get("availability", ""),
        "symptoms":          p.get("symptoms", [])[:5],
        "install_difficulty": p.get("install_difficulty", ""),
        "install_time":       p.get("install_time", ""),
        "video_url":          p.get("video_url", ""),
    }


# ── Tool executor ─────────────────────────────────────────────────────────────

async def execute_tool(tool_name: str, tool_input: dict, session_id: str) -> str:
    try:
        if tool_name == "search_catalog":
            result = await search_catalog(
                query=tool_input["query"],
                category=tool_input.get("category"),
                brand=tool_input.get("brand"),
            )
        elif tool_name == "get_part_details":
            result = await get_part_details(tool_input["part_number"])
        elif tool_name == "check_model_compatibility":
            result = await check_model_compatibility(tool_input["model_number"])
        elif tool_name == "manage_cart":
            result = manage_cart(
                session_id=session_id,
                action=tool_input["action"],
                part_number=tool_input.get("part_number"),
                name=tool_input.get("name"),
                price=tool_input.get("price"),
            )
        elif tool_name == "get_order":
            result = get_order(tool_input.get("order_id"))
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Retry logic ───────────────────────────────────────────────────────────────

_RETRY_DELAYS = [1, 3]  # seconds between attempts on 429 / 529 (max 4s total)
_RETRY_STATUSES = {429, 529}  # rate-limited or overloaded


async def _create_with_retry(client: anthropic.AsyncAnthropic, **kwargs):
    """Call client.messages.create with exponential backoff on transient 4xx/5xx."""
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            await asyncio.sleep(delay)
        try:
            return await client.messages.create(**kwargs)
        except anthropic.APIStatusError as e:
            if e.status_code not in _RETRY_STATUSES:
                raise  # non-retryable (400, 401, 403, etc.)
            last_exc = e
            next_delay = _RETRY_DELAYS[attempt] if attempt < len(_RETRY_DELAYS) else "—"
            print(f"[claude] HTTP {e.status_code} — attempt {attempt + 1}/{len(_RETRY_DELAYS) + 1}, retry in {next_delay}s")
    raise last_exc  # type: ignore[misc]


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _stream_text(text: str):
    """Yield text in word-sized chunks (much fewer SSE frames than char-by-char)."""
    # Split on whitespace but keep the delimiter so words stay readable
    tokens = re.split(r"(\s+)", text)
    buf = ""
    for token in tokens:
        buf += token
        if len(buf) >= 4:          # flush every ~4 chars (word boundary)
            yield buf
            buf = ""
    if buf:
        yield buf


# ── Agent loop ────────────────────────────────────────────────────────────────

async def run_agent(
    messages: list[dict], session_id: str
) -> AsyncGenerator[str, None]:
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    conversation = [{"role": m["role"], "content": m["content"]} for m in messages]

    try:
        while True:
            # ── Call Claude ───────────────────────────────────────────────────
            try:
                response = await _create_with_retry(
                    client,
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=TOOL_DEFINITIONS,
                    messages=conversation,
                )
            except anthropic.APIStatusError as e:
                if e.status_code == 529:
                    msg = "The AI service is temporarily overloaded. Please wait a moment and try again."
                elif e.status_code == 429:
                    msg = "Rate limit reached. Please wait a moment and try again."
                else:
                    msg = f"API error ({e.status_code}). Please try again."
                yield _sse({"type": "text", "content": msg})
                yield _sse({"type": "done", "content": ""})
                return

            # ── Parse response blocks ─────────────────────────────────────────
            text_content = ""
            tool_uses    = []
            for block in response.content:
                if block.type == "text":
                    text_content += block.text
                elif block.type == "tool_use":
                    tool_uses.append(block)

            # Notify frontend which tools are running
            for tool_use in tool_uses:
                yield _sse({"type": "tool_call", "content": tool_use.name})

            # ── Final text response — no more tool calls ──────────────────────
            if not tool_uses:
                for chunk in _stream_text(text_content):
                    yield _sse({"type": "text", "content": chunk})
                yield _sse({"type": "done", "content": ""})
                return

            # ── Execute tools ─────────────────────────────────────────────────
            conversation.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tool_use in tool_uses:
                result_str = await execute_tool(tool_use.name, tool_use.input, session_id)
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": tool_use.id,
                    "content":     result_str,
                })

                # Emit product card events to the frontend
                try:
                    parsed = json.loads(result_str)
                    parts_to_emit: list[dict] = []

                    if tool_use.name == "search_catalog" and isinstance(parsed, list):
                        parts_to_emit = [
                            _normalise_part(p) for p in parsed
                            if p.get("part_number") and p.get("type", "part") == "part"
                        ]

                    elif tool_use.name == "get_part_details" and isinstance(parsed, dict):
                        if parsed.get("part_number") and not parsed.get("error"):
                            parts_to_emit = [_normalise_part(parsed)]

                    elif tool_use.name == "check_model_compatibility" and isinstance(parsed, dict):
                        parts_to_emit = [
                            _normalise_part(p)
                            for p in parsed.get("compatible_parts", [])
                            if p.get("part_number")
                        ]

                    if parts_to_emit:
                        yield _sse({"type": "parts", "content": parts_to_emit})

                except Exception:
                    pass

            conversation.append({"role": "user", "content": tool_results})
            # Loop — Claude will now see tool results and produce next response

    except Exception as e:
        # Safety net: any exception that escapes the inner handlers becomes a
        # clean error SSE so the ASGI connection is never left undefined.
        print(f"[run_agent] fatal: {type(e).__name__}: {e}")
        yield _sse({"type": "text", "content": "An unexpected error occurred. Please try again."})
        yield _sse({"type": "done", "content": ""})
