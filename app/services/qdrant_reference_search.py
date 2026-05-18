from __future__ import annotations

import uuid
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PointStruct, VectorParams


def qdrant_client(url: str) -> QdrantClient:
    return QdrantClient(url=url, prefer_grpc=False)


def ensure_collection(client: QdrantClient, *, collection: str, vector_size: int) -> None:
    """Create the collection if it does not exist yet."""

    try:
        if client.collection_exists(collection):
            return

    except UnexpectedResponse:
        pass

    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def ingest_reference(
    client: QdrantClient,
    *,
    collection: str,
    vector_size: int,
    image_url: str,
    description: str,
    vector: list[float],
    tags: list[str] | None = None,
    point_id: str | None = None,
) -> str:
    """Upsert one reference image into Qdrant. Returns the point id."""

    ensure_collection(client, collection=collection, vector_size=vector_size)
    pid = point_id or str(uuid.uuid4())

    payload: dict[str, Any] = {
        "image_url": image_url,
        "description": description,
        "tags": tags or [],
    }

    client.upsert(
        collection_name=collection,
        points=[PointStruct(id=pid, vector=vector, payload=payload)],
    )

    return pid


def search_references(
    client: QdrantClient,
    *,
    collection: str,
    query_vector: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    """Return payloads for nearest neighbours (expects payload with at least `image_url` or `url`)."""

    try:
        exists = client.collection_exists(collection)
    except UnexpectedResponse:
        return []

    if not exists:
        return []

    resp = client.query_points(
        collection_name=collection,
        query=query_vector,
        limit=limit,
        with_payload=True,
    )

    hits = resp.points

    out: list[dict[str, Any]] = []

    for h in hits:
        payload = h.payload or {}
        row = {"score": h.score, **dict(payload)}
        out.append(row)

    return out


def reference_image_urls(rows: list[dict[str, Any]], *, max_refs: int) -> list[str]:
    urls: list[str] = []

    for row in rows:
        url: Optional[str] = None
        for key in ("image_url", "url", "src"):
            v = row.get(key)
            if isinstance(v, str) and (v.startswith("http") or v.startswith("data:image")):
                url = v
                break

        if url and url not in urls:
            urls.append(url)
        if len(urls) >= max_refs:
            break

    return urls
