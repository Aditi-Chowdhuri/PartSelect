"""
Embed scraped parts and build a local FAISS index.
No API keys required — uses sentence-transformers (free, runs locally).

Run from the scraper/ directory: python embed_and_index.py
Input:  data/parts_raw.json       (output of scrape_parts.py)
Output: ../backend/app/data/faiss_index.bin     — FAISS cosine-similarity index
        ../backend/app/data/parts_metadata.json  — ordered part metadata

Model: all-MiniLM-L6-v2 (~90 MB, downloads once to HuggingFace cache)
Dim:   384
"""
import json
import numpy as np
from pathlib import Path

import faiss
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64
OUT_DIR    = Path("../backend/app/data")


def make_embedding_text(part: dict) -> str:
    symptoms = "; ".join(part.get("symptoms", [])[:5])
    models   = ", ".join(part.get("compatible_models", [])[:10])
    pieces = [
        part.get("name", ""),
        part.get("description", "")[:300],
        f"Symptoms: {symptoms}" if symptoms else "",
        f"Brand: {part.get('brand', '')}",
        f"Category: {part.get('category', '')} parts",
        f"Part number: {part.get('part_number', '')}",
        f"Compatible with: {models}" if models else "",
        f"Replaces: {', '.join(part.get('replaces', [])[:5])}" if part.get("replaces") else "",
    ]
    return " ".join(p for p in pieces if p).strip()


def build_metadata(part: dict) -> dict:
    return {
        "part_number":       part.get("part_number", ""),
        "mpn":               part.get("mpn", ""),
        "name":              part.get("name", ""),
        "price":             float(part.get("price", 0.0)),
        "brand":             part.get("brand", ""),
        "category":          part.get("category", ""),
        "image_url":         part.get("image_url", ""),
        "description":       part.get("description", "")[:300],
        "rating":            float(part.get("rating", 0.0)),
        "review_count":      int(part.get("review_count", 0)),
        "url":               part.get("url", ""),
        "symptoms":          part.get("symptoms", [])[:10],
        "install_difficulty":part.get("install_difficulty", ""),
        "install_time":      part.get("install_time", ""),
        "video_url":         part.get("video_url", ""),
        "availability":      part.get("availability", ""),
        "replaces":          part.get("replaces", [])[:10],
        "compatible_models_str": ", ".join(part.get("compatible_models", [])[:30])[:1000],
    }


def make_repair_text(repair: dict) -> str:
    # Handle both old format (parts=list[str]) and new format (parts=list[dict])
    raw_parts = repair.get("parts", [])
    if raw_parts and isinstance(raw_parts[0], dict):
        parts_str = ", ".join(p.get("part_number", "") + " " + p.get("name", "") for p in raw_parts)
    else:
        parts_str = ", ".join(raw_parts)
    return (
        f"{repair.get('symptom', '')} {repair.get('description', '')} "
        f"Category: {repair.get('category', '')}. "
        f"Brand: {repair.get('brand', '')}. "
        f"Related parts: {parts_str}. "
        f"Difficulty: {repair.get('difficulty', '')}."
    ).strip()


def build_repair_metadata(repair: dict) -> dict:
    raw_parts = repair.get("parts", [])
    if raw_parts and isinstance(raw_parts[0], dict):
        parts_list = [p.get("part_number", "") for p in raw_parts if p.get("part_number")]
    else:
        parts_list = raw_parts
    return {
        "type":        "repair",
        "category":    repair.get("category", ""),
        "brand":       repair.get("brand", ""),
        "symptom":     repair.get("symptom", ""),
        "description": repair.get("description", ""),
        "frequency":   repair.get("frequency", ""),
        "parts":       parts_list,
        "difficulty":  repair.get("difficulty", repair.get("repair_time", "")),
        "video_url":   repair.get("video_url", ""),
        "url":         repair.get("url", ""),
        "tips":        repair.get("tips", [])[:5],
        # dummy fields so backend metadata shape is consistent
        "part_number": "",
        "name":        repair.get("symptom", ""),
        "price":       0.0,
        "image_url":   "",
    }


def make_blog_text(blog: dict) -> str:
    return (
        f"{blog.get('title', '')} "
        f"Category: {blog.get('category', '')}. "
        f"{blog.get('content', '')[:500]}"
    ).strip()


def build_blog_metadata(blog: dict) -> dict:
    return {
        "type":        "blog",
        "category":    blog.get("category", ""),
        "name":        blog.get("title", ""),
        "description": blog.get("content", "")[:300],
        "url":         blog.get("url", ""),
        "pub_date":    blog.get("pub_date", ""),
        "part_numbers": blog.get("part_numbers", []),
        # dummy fields for consistent shape
        "part_number": "",
        "price":       0.0,
        "brand":       "",
        "image_url":   "",
        "symptom":     "",
        "parts":       blog.get("part_numbers", []),
        "difficulty":  "",
        "video_url":   "",
        "frequency":   "",
    }


def main() -> None:
    raw_path = Path("data/parts_raw.json")
    if not raw_path.exists():
        raise FileNotFoundError("data/parts_raw.json not found -- run scrape_parts.py first")

    parts = json.loads(raw_path.read_text(encoding="utf-8", errors="replace"))
    parts = [p for p in parts if p.get("part_number") and p.get("name")]
    print(f"Loaded {len(parts)} valid parts")

    # Load repairs if available
    repairs_path = Path("data/repairs_raw.json")
    repairs: list[dict] = []
    if repairs_path.exists():
        repairs = json.loads(repairs_path.read_text(encoding="utf-8", errors="replace"))
        print(f"Loaded {len(repairs)} repair guides")
    else:
        print("No repairs_raw.json — run scrape_repairs.py to add repair guides")

    # Load blog articles if available
    blogs_path = Path("data/blogs_raw.json")
    blogs: list[dict] = []
    if blogs_path.exists():
        blogs = json.loads(blogs_path.read_text(encoding="utf-8", errors="replace"))
        print(f"Loaded {len(blogs)} blog articles")
    else:
        print("No blogs_raw.json — run scrape_blogs.py to add blog content")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load model ────────────────────────────────────────────────────────────
    print(f"\nLoading model '{MODEL_NAME}' (downloads ~90 MB once if not cached)...")
    model = SentenceTransformer(MODEL_NAME)

    # ── Build embedding texts (order must match metadata) ─────────────────────
    part_texts   = [make_embedding_text(p) for p in parts]
    repair_texts = [make_repair_text(r)    for r in repairs]
    blog_texts   = [make_blog_text(b)      for b in blogs]
    all_texts    = part_texts + repair_texts + blog_texts

    print(f"Embedding {len(part_texts)} parts + {len(repair_texts)} repairs + {len(blog_texts)} blogs...")
    embeddings = model.encode(
        all_texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    print(f"Embeddings shape: {embeddings.shape}")

    # ── Build FAISS index ─────────────────────────────────────────────────────
    dim   = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))

    index_path = OUT_DIR / "faiss_index.bin"
    faiss.write_index(index, str(index_path))
    print(f"\nSaved FAISS index ({index.ntotal} vectors) to {index_path}")

    # ── Save metadata (order must match index) ────────────────────────────────
    part_meta   = [build_metadata(p)        for p in parts]
    repair_meta = [build_repair_metadata(r) for r in repairs]
    blog_meta   = [build_blog_metadata(b)   for b in blogs]
    all_meta    = part_meta + repair_meta + blog_meta

    meta_path = OUT_DIR / "parts_metadata.json"
    meta_path.write_text(json.dumps(all_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved metadata ({len(part_meta)} parts + {len(repair_meta)} repairs + {len(blog_meta)} blogs) to {meta_path}")

    # ── Sanity checks ─────────────────────────────────────────────────────────
    for query in ["ice maker not working", "dishwasher not draining", "leaking refrigerator"]:
        q_vec = model.encode([query], normalize_embeddings=True).astype(np.float32)
        scores, idxs = index.search(q_vec, 3)
        print(f"\nTop 3 for '{query}':")
        for score, idx in zip(scores[0], idxs[0]):
            m = all_meta[idx]
            label = m.get("part_number") or m.get("symptom") or m.get("name", "?")
            mtype = m.get("type", "part")
            print(f"  [{score:.3f}] [{mtype}] {label} ({m.get('category','')})")

    print("\nDone! Restart the FastAPI backend to load the new index.")


if __name__ == "__main__":
    main()
