"""
Embed scraped parts and build a local FAISS index.
No API keys required — uses sentence-transformers (free, runs locally).

Run from the scraper/ directory: python embed_and_index.py
Input:  data/parts_raw.json
Output: ../backend/app/data/faiss_index.bin
        ../backend/app/data/parts_metadata.json
        ../backend/app/data/model_part_map.json

Model: all-MiniLM-L6-v2 (~90 MB, downloads once to HuggingFace cache)
"""
import json
import numpy as np
from pathlib import Path

import faiss
from sentence_transformers import SentenceTransformer

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
        "part_number":        part.get("part_number", ""),
        "mpn":                part.get("mpn", ""),
        "name":               part.get("name", ""),
        "price":              float(part.get("price", 0.0)),
        "brand":              part.get("brand", ""),
        "category":           part.get("category", ""),
        "image_url":          part.get("image_url", ""),
        "description":        part.get("description", "")[:300],
        "rating":             float(part.get("rating", 0.0)),
        "review_count":       int(part.get("review_count", 0)),
        "url":                part.get("url", ""),
        "symptoms":           part.get("symptoms", [])[:10],
        "install_difficulty": part.get("install_difficulty", ""),
        "install_time":       part.get("install_time", ""),
        "video_url":          part.get("video_url", ""),
        "availability":       part.get("availability", ""),
        "replaces":           part.get("replaces", [])[:10],
        "compatible_models_str": ", ".join(part.get("compatible_models", [])[:30])[:1000],
    }


def main() -> None:
    raw_path = Path("data/parts_raw.json")
    if not raw_path.exists():
        raise FileNotFoundError("data/parts_raw.json not found — run scrape_parts.py first")

    parts = json.loads(raw_path.read_text(encoding="utf-8", errors="replace"))
    parts = [p for p in parts if p.get("part_number") and p.get("name")]
    print(f"Loaded {len(parts)} valid parts")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nLoading sentence-transformer '{MODEL_NAME}' (downloads ~90 MB once)...")
    model = SentenceTransformer(MODEL_NAME)

    texts = [make_embedding_text(p) for p in parts]
    print(f"Embedding {len(texts)} parts...")
    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    print(f"Embeddings shape: {embeddings.shape}")

    # FAISS index (cosine similarity via inner product on normalised vectors)
    dim   = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))

    index_path = OUT_DIR / "faiss_index.bin"
    faiss.write_index(index, str(index_path))
    print(f"\nSaved FAISS index ({index.ntotal} vectors) -> {index_path}")

    meta     = [build_metadata(p) for p in parts]
    meta_path = OUT_DIR / "parts_metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved metadata ({len(meta)} parts) -> {meta_path}")

    # Quick sanity checks
    for query in ["ice maker not working", "dishwasher not draining", "water leaking fridge"]:
        q_vec = model.encode([query], normalize_embeddings=True).astype(np.float32)
        scores, idxs = index.search(q_vec, 3)
        print(f"\nTop 3 for '{query}':")
        for score, idx in zip(scores[0], idxs[0]):
            m = meta[idx]
            print(f"  [{score:.3f}] {m['part_number']} {m['name']} ({m['category']})")

    # Copy relational data files used by the backend to backend/app/data/
    data_files_to_copy = [
        "model_part_map.json",
        "symptom_part_map.json",
        "part_type_map.json",
        "brand_appliance_map.json",
    ]
    for fname in data_files_to_copy:
        src = Path("data") / fname
        if src.exists():
            dst = OUT_DIR / fname
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"Copied {fname} -> {dst}")
        else:
            print(f"SKIP {fname} (not found)")

    print("\nDone. Restart the FastAPI backend to load the new index.")


if __name__ == "__main__":
    main()
