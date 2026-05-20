from __future__ import annotations

import uuid
from typing import Any

from app.config import settings
from app.services.dashscope_qwen import DashScopeClient
from app.services.qdrant_reference_search import QdrantReferenceSearch


class ReferenceLibrary:
    """Style-reference library: embeds reference images and stores them in Qdrant."""

    LIBRARY_POINT_NAMESPACE = uuid.UUID("a3f2c8d1-6e4b-4f7a-9c2d-1b8e5f4a3c6d")

    def __init__(self) -> None:
        self.search = QdrantReferenceSearch(
            url=settings.qdrant_url,
            collection=settings.qdrant_collection,
            vector_size=settings.qwen_embedding_vector_size,
        )

    @classmethod
    def stable_point_id(cls, image_url: str) -> str:
        """Deterministic Qdrant point id so re-ingesting the same image updates in place."""

        return str(uuid.uuid5(cls.LIBRARY_POINT_NAMESPACE, image_url.strip()))

    @staticmethod
    def _describe_reference_image(client: DashScopeClient, *, image_url: str) -> str:
        result = client.multimodal_chat_text(
            model=settings.qwen_vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"image": image_url},
                        {
                            "text": (
                                "Describe this image in 1–3 sentences focusing on style, "
                                "clothing items, colours, textures, and mood. Be concise."
                            )
                        },
                    ],
                }
            ],
        )
        return result.strip()

    def ingest(
        self,
        *,
        image_url: str,
        description: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Embed a reference image into Qdrant and return the stored record."""

        api_key = settings.dashscope_reasoning_key()
        if not api_key:
            raise ValueError("Set DASHSCOPE_API_KEY to ingest references.")

        client = DashScopeClient(
            api_key=api_key,
            base_http_api_url=settings.dashscope_reasoning_base(),
        )

        desc = description.strip()
        if not desc:
            desc = self._describe_reference_image(client, image_url=image_url)

        vector = client.embed_text(
            model=settings.qwen_embedding_model,
            text=desc,
            text_type="document",
        )

        tag_list = list(tags or [])
        point_id = self.stable_point_id(image_url)
        self.search.ingest_reference(
            image_url=image_url,
            description=desc,
            vector=vector,
            tags=tag_list,
            point_id=point_id,
        )

        return {
            "point_id": point_id,
            "image_url": image_url,
            "description": desc,
            "tags": tag_list,
        }

    def list(self, *, limit: int = 256) -> list[dict[str, Any]]:
        """Return all references stored in the Qdrant style library."""

        if not self.search.collection_exists():
            return []

        rows: list[dict[str, Any]] = []
        offset = None

        while len(rows) < limit:
            batch_limit = min(64, limit - len(rows))
            points, offset = self.search.client.scroll(
                collection_name=self.search.collection,
                limit=batch_limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            if not points:
                break

            for point in points:
                payload = dict(point.payload or {})
                image_url = payload.get("image_url")
                if not isinstance(image_url, str):
                    continue
                if not (image_url.startswith("http") or image_url.startswith("data:image")):
                    continue

                description = payload.get("description")
                raw_tags = payload.get("tags")
                tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []

                rows.append(
                    {
                        "point_id": str(point.id),
                        "image_url": image_url,
                        "description": description if isinstance(description, str) else "",
                        "tags": tags,
                    }
                )

            if offset is None:
                break

        rows.sort(key=lambda r: r.get("description", "").lower())
        return rows
