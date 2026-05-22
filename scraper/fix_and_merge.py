"""
fix_and_merge.py

1. For each part in parts_raw.json, fetches the real canonical URL from Wayback CDX.
2. Falls back to the constructed URL if CDX returns nothing.
3. Normalises to https://.
4. Saves cleaned parts_raw.json + parts_raw.jsonl.
5. Merges parts + repairs + blogs into data/all_data.json.

Run: python fix_and_merge.py
"""
import asyncio
import json
import re
import time
from pathlib import Path

import httpx

PARTS_PATH   = Path("data/parts_raw.json")
REPAIRS_PATH = Path("data/repairs_raw.json")
BLOGS_PATH   = Path("data/blogs_raw.json")
OUT_PARTS    = Path("data/parts_raw.json")
OUT_JSONL    = Path("data/parts_raw.jsonl")
OUT_MERGED   = Path("data/all_data.json")


def to_https(url: str) -> str:
    return url.replace("http://", "https://", 1) if url else url


async def cdx_url(client: httpx.AsyncClient, pn: str) -> str:
    """Return the real canonical URL for a PS part number from Wayback CDX."""
    for attempt in range(3):
        try:
            r = await client.get(
                "https://web.archive.org/cdx/search/cdx",
                params={
                    "url":      f"www.partselect.com/{pn}*",
                    "output":   "json",
                    "fl":       "original",
                    "filter":   "statuscode:200",
                    "limit":    1,
                    "collapse": "original",
                },
                timeout=15,
            )
            rows = r.json()
            if len(rows) >= 2:
                raw = rows[1][0].split("?")[0]
                return to_https(raw)
        except Exception:
            await asyncio.sleep(2 * (attempt + 1))
    return ""


async def fix_urls(parts: list[dict]) -> list[dict]:
    fixed = []
    async with httpx.AsyncClient() as client:
        for i, p in enumerate(parts):
            pn = p["part_number"]
            real = await cdx_url(client, pn)
            old  = p.get("url", "")
            if real and real != old:
                print(f"  [{i+1}/{len(parts)}] {pn}: fixed URL")
                print(f"    old: {old}")
                print(f"    new: {real}")
                p["url"] = real
            elif real:
                print(f"  [{i+1}/{len(parts)}] {pn}: OK {real}")
            else:
                print(f"  [{i+1}/{len(parts)}] {pn}: CDX miss — keeping {old}")
            fixed.append(p)
            await asyncio.sleep(0.4)
    return fixed


async def main() -> None:
    parts   = json.loads(PARTS_PATH.read_text(encoding="utf-8"))
    repairs = json.loads(REPAIRS_PATH.read_text(encoding="utf-8")) if REPAIRS_PATH.exists() else []
    blogs   = json.loads(BLOGS_PATH.read_text(encoding="utf-8"))   if BLOGS_PATH.exists()   else []

    print(f"Loaded {len(parts)} parts, {len(repairs)} repairs, {len(blogs)} blogs")
    print("\n=== Fixing part URLs via Wayback CDX ===")
    parts = await fix_urls(parts)

    # Save cleaned parts
    OUT_PARTS.write_text(json.dumps(parts, indent=2, ensure_ascii=False), encoding="utf-8")
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for p in parts:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"\nSaved {len(parts)} parts to {OUT_PARTS} and {OUT_JSONL}")

    # Add type tags
    for p in parts:
        p.setdefault("type", "part")
    for r in repairs:
        r.setdefault("type", "repair")
    for b in blogs:
        b.setdefault("type", "blog")

    merged = parts + repairs + blogs
    OUT_MERGED.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved merged {len(merged)} records to {OUT_MERGED}")
    print(f"  parts: {len(parts)}  repairs: {len(repairs)}  blogs: {len(blogs)}")

    # Sanity check — show any parts still with short URLs
    bad = [p for p in parts if p.get("url","").count("-") == 0]
    if bad:
        print(f"\nWARNING: {len(bad)} parts still have short URLs:")
        for p in bad:
            print(f"  {p['part_number']}: {p.get('url','')}")
    else:
        print("\nAll part URLs have slug (looks correct).")


if __name__ == "__main__":
    asyncio.run(main())
