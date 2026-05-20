from __future__ import annotations

import uuid
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PointStruct, VectorParams


class QdrantReferenceSearch:
    """Reference-image vector store backed by a single Qdrant collection."""

    def __init__(self, *, url: str, collection: str, vector_size: int) -> None:
        self.collection = collection
        self.vector_size = vector_size
        self.client = QdrantClient(url=url, prefer_grpc=False)

    def ensure_collection(self) -> None:
        """Create the collection if it does not exist yet."""

        try:
            if self.client.collection_exists(self.collection):
                return

        except UnexpectedResponse:
            pass

        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
        )

    def collection_exists(self) -> bool:
        try:
            return self.client.collection_exists(self.collection)
        except UnexpectedResponse:
            return False

    def ingest_reference(
        self,
        *,
        image_url: str,
        description: str,
        vector: list[float],
        tags: list[str] | None = None,
        point_id: str | None = None,
    ) -> str:
        """Upsert one reference image into Qdrant. Returns the point id."""

        self.ensure_collection()
        pid = point_id or str(uuid.uuid4())

        payload: dict[str, Any] = {
            "image_url": image_url,
            "description": description,
            "tags": tags or [],
        }

        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=pid, vector=vector, payload=payload)],
        )

        return pid

    def search_references(
        self,
        *,
        query_vector: list[float],
        limit: int,
    ) -> list[dict[str, Any]]:
        """Return payloads for nearest neighbours (expects payload with at least `image_url` or `url`)."""

        if not self.collection_exists():
            return []

        resp = self.client.query_points(
            collection_name=self.collection,
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

    @staticmethod
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

    def list_references(self) -> list[dict[str, Any]]:
        """Return all references in the collection."""

        return self.client.list_collections(collection_name=self.collection)
