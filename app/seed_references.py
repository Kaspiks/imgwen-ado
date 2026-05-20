"""Seed Qdrant with the built-in style-exploration reference images.

Run once (idempotent — uses stable point IDs so re-runs overwrite, not duplicate).
Requires DASHSCOPE_API_KEY and a running Qdrant instance.

Usage:
    python -m app.seed_references
"""

from __future__ import annotations

import base64
import mimetypes
import sys
import uuid
from pathlib import Path

from app.config import settings
from app.services.dashscope_qwen import DashScopeClient
from app.services.qdrant_reference_search import QdrantReferenceSearch

FRONTEND_PUBLIC = Path(__file__).resolve().parent.parent / "frontend" / "public"
SEED_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

REFERENCES: list[dict[str, object]] = [
    {
        "file": "1294.png",
        "seed_key": "ref-seed-blue-tones-palette",
        "description": (
            "A monochromatic color palette spanning from deep navy to light sky blue. "
            "Five vertical swatches: navy, teal, steel blue, sky blue, and ice. "
            "Useful as a color reference for cool-toned edits, backgrounds, and brand palettes."
        ),
        "tags": ["color palette", "blue", "cool tones", "monochromatic", "minimal"],
    },
    {
        "file": "photo_2026-05-18_09-36-43.jpg",
        "seed_key": "ref-seed-minimalism-interior",
        "description": (
            "Satin ribbon roses in blush pink and sky blue wrapped in white paper, "
            "alongside a black candle gift box with pebbles. Minimalist interior styling "
            "reference with soft textures, curated pastel color story, and overhead composition."
        ),
        "tags": ["minimalism", "interior", "pastel", "pink", "blue", "styling", "texture"],
    },
]


def _file_to_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    raw = path.read_bytes()
    b64 = base64.standard_b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def main() -> None:
    api_key = settings.dashscope_reasoning_key()
    if not api_key:
        print("[seed_references] No DASHSCOPE_API_KEY set — skipping Qdrant seed.")
        return

    search = QdrantReferenceSearch(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        vector_size=settings.qwen_embedding_vector_size,
    )

    client = DashScopeClient(
        api_key=api_key,
        base_http_api_url=settings.dashscope_reasoning_base(),
    )

    model = settings.qwen_embedding_model

    seeded = 0
    for ref in REFERENCES:
        file_path = FRONTEND_PUBLIC / str(ref["file"])
        if not file_path.exists():
            print(f"[seed_references] File not found: {file_path} — skipping.")
            continue

        description = str(ref["description"])
        tags = list(ref.get("tags") or [])
        seed_key = str(ref["seed_key"])
        point_id = str(uuid.uuid5(SEED_NAMESPACE, seed_key))

        data_uri = _file_to_data_uri(file_path)

        try:
            vector = client.embed_text(
                model=model,
                text=description,
                text_type="document",
            )

        except Exception as exc:
            print(f"[seed_references] Embedding failed for {ref['file']}: {exc}")
            continue

        try:
            search.ingest_reference(
                image_url=data_uri,
                description=description,
                vector=vector,
                tags=tags,
                point_id=point_id,
            )

            seeded += 1
            print(f"[seed_references] Ingested {ref['file']} as {point_id}")
        except Exception as exc:
            print(f"[seed_references] Qdrant upsert failed for {ref['file']}: {exc}")

    print(f"[seed_references] Done — {seeded}/{len(REFERENCES)} references seeded.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
