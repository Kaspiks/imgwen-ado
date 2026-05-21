"""MinIO-backed image storage.

Persisted image URLs are short, browser-reachable MinIO URLs
(``{minio_public_url}/{bucket}/{key}``). DashScope cannot reach a local MinIO,
so the backend resolves these URLs back to inline ``data:`` URIs at call time
via :func:`resolve_for_model` — the bytes are inlined only transiently, never
stored. This keeps the DB, Qdrant payloads, and LLM prompts small while still
feeding the model the image content it needs.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import mimetypes
import urllib.request
import uuid
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)

_EXT_BY_CT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# Cap on bytes we will download/inline for a single image.
_MAX_IMAGE_BYTES = 10 * 1024 * 1024


class ObjectStorage:
    """Thin wrapper around a single MinIO bucket for image blobs."""

    def __init__(self) -> None:
        self.bucket = settings.minio_bucket
        self.public_base = settings.minio_public_url.rstrip("/")
        scheme = "https" if settings.minio_secure else "http"
        # Origins that identify a URL as belonging to our bucket (browser-facing public
        # base and the internal endpoint), each suffixed with the bucket path.
        self._owned_prefixes = tuple(
            f"{origin}/{self.bucket}/"
            for origin in {self.public_base, f"{scheme}://{settings.minio_endpoint}"}
        )
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket_ready = False

    # -- bucket lifecycle ---------------------------------------------------

    def ensure_bucket(self) -> None:
        """Create the bucket (idempotent) and grant anonymous read so the browser
        can fetch images directly. Safe to call repeatedly."""
        if self._bucket_ready:
            return
        if not self._client.bucket_exists(self.bucket):
            self._client.make_bucket(self.bucket)
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self.bucket}/*"],
                }
            ],
        }
        try:
            self._client.set_bucket_policy(self.bucket, json.dumps(policy))
        except S3Error:
            logger.warning("Could not set public-read policy on bucket %s", self.bucket, exc_info=True)
        self._bucket_ready = True

    # -- url helpers --------------------------------------------------------

    def public_url(self, key: str) -> str:
        return f"{self.public_base}/{self.bucket}/{key}"

    def object_key_for(self, url: str) -> Optional[str]:
        """Return the object key if ``url`` points at our MinIO bucket, else None.

        Matches the configured public base or the internal endpoint origin so that
        unrelated URLs that merely contain ``/{bucket}/`` are not misclassified.
        """
        u = (url or "").strip()
        if not u:
            return None
        for prefix in self._owned_prefixes:
            if u.startswith(prefix):
                key = u[len(prefix) :].split("?", 1)[0]
                return key or None
        return None

    # -- blob io ------------------------------------------------------------

    def put_bytes(self, raw: bytes, *, content_type: str) -> str:
        """Upload bytes and return the public URL."""
        self.ensure_bucket()
        ct = (content_type or "").split(";")[0].strip().lower() or "image/png"
        ext = _EXT_BY_CT.get(ct, mimetypes.guess_extension(ct) or ".bin")
        key = f"{uuid.uuid4().hex}{ext}"
        self._client.put_object(
            self.bucket,
            key,
            data=io.BytesIO(raw),
            length=len(raw),
            content_type=ct,
        )
        return self.public_url(key)

    def get_bytes(self, key: str) -> tuple[bytes, str]:
        """Return (raw_bytes, content_type) for an object in this bucket."""
        resp = self._client.get_object(self.bucket, key)
        try:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "image/png")
        finally:
            resp.close()
            resp.release_conn()
        return raw, ct


_storage: Optional[ObjectStorage] = None


def storage() -> ObjectStorage:
    global _storage
    if _storage is None:
        _storage = ObjectStorage()
    return _storage


def _decode_data_uri(url: str) -> Optional[tuple[bytes, str]]:
    """Decode a ``data:<ct>;base64,<payload>`` URL into (bytes, content_type)."""
    if not url.startswith("data:"):
        return None
    try:
        header, b64 = url.split(",", 1)
        ct = header[5:].split(";", 1)[0] or "image/png"
        return base64.b64decode(b64), ct
    except Exception:
        logger.warning("Could not decode data: URI for storage", exc_info=True)
        return None


def persist(url: str, *, max_bytes: int = _MAX_IMAGE_BYTES) -> str:
    """Store an image in MinIO and return its public URL.

    - ``data:`` URI → decode bytes, upload, return MinIO URL.
    - already a MinIO URL for our bucket → returned unchanged.
    - other http(s) URL (e.g. a short-lived DashScope OSS URL) → download, upload,
      return MinIO URL so the persisted reference never expires.

    On any failure, returns the input URL unchanged so the flow degrades gracefully.
    """
    u = (url or "").strip()
    if not u:
        return u

    try:
        s = storage()
    except Exception:
        logger.warning("Object storage unavailable; keeping original URL", exc_info=True)
        return u

    # Already ours — nothing to do.
    if s.object_key_for(u):
        return u

    decoded = _decode_data_uri(u)
    if decoded is not None:
        raw, ct = decoded
        if len(raw) > max_bytes:
            logger.warning("Image exceeds %d bytes; keeping data URI", max_bytes)
            return u
        try:
            return s.put_bytes(raw, content_type=ct)
        except Exception:
            logger.warning("MinIO upload failed for data URI; keeping original", exc_info=True)
            return u

    if u.startswith("http://") or u.startswith("https://"):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "imgwen/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 - DashScope OSS URLs
                ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                raw = resp.read(max_bytes + 1)
        except Exception:
            logger.warning("Could not fetch image for persistence: %s", u[:120], exc_info=True)
            return u
        if len(raw) > max_bytes:
            logger.warning("Image too large to store (>%d bytes); keeping original URL", max_bytes)
            return u
        if not ct.startswith("image/"):
            ct = "image/png"
        try:
            return s.put_bytes(raw, content_type=ct)
        except Exception:
            logger.warning("MinIO upload failed for remote URL; keeping original", exc_info=True)
            return u

    return u


def resolve_for_model(url: str) -> str:
    """Return a URL DashScope can consume.

    Our MinIO URLs are not reachable from Alibaba's servers, so they are fetched
    from MinIO and returned as an inline ``data:`` URI. ``data:`` URIs and other
    (public) http(s) URLs are returned unchanged.
    """
    u = (url or "").strip()
    if not u or u.startswith("data:"):
        return u

    try:
        s = storage()
        key = s.object_key_for(u)
    except Exception:
        return u

    if not key:
        return u

    try:
        raw, ct = s.get_bytes(key)
    except Exception:
        logger.warning("Could not fetch %s from MinIO for model call", key, exc_info=True)
        return u

    if not ct.startswith("image/"):
        ct = "image/png"
    b64 = base64.standard_b64encode(raw).decode("ascii")
    return f"data:{ct};base64,{b64}"


def resolve_many(urls: list[str]) -> list[str]:
    return [resolve_for_model(u) for u in urls]
