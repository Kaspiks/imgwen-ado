from __future__ import annotations

import base64
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.edit_flow import (
    EditFlowChatRequest,
    EditFlowChatResponse,
    EditFlowMessageOut,
    EditFlowReferencesRequest,
    EditFlowReferencesResponse,
    EditFlowRunEditResponse,
    EditFlowSessionCreate,
    EditFlowSessionOut,
    ImageUploadResponse,
    ReferenceIngestRequest,
    ReferenceIngestResponse,
)
from app.services import dashscope_qwen as dq
from app.services import edit_flow_service as efs
from app.services.qdrant_reference_search import ingest_reference, qdrant_client

router = APIRouter(prefix="/workflow/edit-flow", tags=["edit-flow"])


def _normalize_ref_urls(urls: list[str], *, max_refs: int = 2) -> list[str]:
    out: list[str] = []
    for u in urls:
        u2 = (u or "").strip()
        if (u2.startswith("http") or u2.startswith("data:image")) and u2 not in out:
            out.append(u2)
        if len(out) >= max_refs:
            break
    return out


ALLOWED_IMAGE_CT = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif"},
)
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def _session_out(db: Session, session_id: int) -> EditFlowSessionOut:
    s = efs.get_edit_flow_session(db, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = efs.list_session_messages(db, session_id)
    return EditFlowSessionOut(
        id=s.id,
        phase=s.phase.value,
        base_image_url=s.base_image_url,
        reference_urls=list(s.reference_urls or []),
        messages=[
            EditFlowMessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                reference_urls=list(m.reference_urls or []),
            )
            for m in msgs
        ],
        last_edit_result=s.last_edit_result,
    )


@router.post("/upload", response_model=ImageUploadResponse)
async def upload_image(file: UploadFile = File(...)) -> ImageUploadResponse:
    """Upload a local image; returns a data URL usable as base_image_url or reference (no public hosting required)."""
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 2MB for embedded data URLs).")
    ct = (file.content_type or "application/octet-stream").split(";")[0].strip().lower()
    if ct not in ALLOWED_IMAGE_CT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type {file.content_type!r}. Use JPEG, PNG, WebP, or GIF.",
        )
    b64 = base64.standard_b64encode(raw).decode("ascii")
    data_url = f"data:{ct};base64,{b64}"
    return ImageUploadResponse(url=data_url, content_type=ct, size_bytes=len(raw))


@router.post("/references/ingest", response_model=ReferenceIngestResponse)
def post_ingest_reference(body: ReferenceIngestRequest) -> ReferenceIngestResponse:
    """Embed a reference image into Qdrant for future retrieval.

    If *description* is empty the VL model describes the image automatically.
    The embedding is generated from the description text and stored with the image URL.
    """
    from app.config import settings

    reasoning_key = settings.dashscope_reasoning_key()
    if not reasoning_key:
        raise HTTPException(status_code=400, detail="Set DASHSCOPE_API_KEY to ingest references.")

    description = body.description.strip()

    if not description:
        try:
            result = dq.multimodal_chat_text(
                api_key=reasoning_key,
                base_http_api_url=settings.dashscope_reasoning_base(),
                model=settings.qwen_vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"image": body.image_url},
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
            description = result.strip()
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Auto-description failed (provide description manually): {exc}",
            ) from exc

    try:
        vector = dq.embed_text(
            api_key=reasoning_key,
            base_http_api_url=settings.dashscope_reasoning_base(),
            model=settings.qwen_embedding_model,
            text=description,
            text_type="document",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Embedding failed: {exc}") from exc

    try:
        qclient = qdrant_client(settings.qdrant_url)
        pid = ingest_reference(
            qclient,
            collection=settings.qdrant_collection,
            vector_size=settings.qwen_embedding_vector_size,
            image_url=body.image_url,
            description=description,
            vector=vector,
            tags=list(body.tags),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Qdrant upsert failed: {exc}") from exc

    return ReferenceIngestResponse(
        point_id=pid,
        description=description,
        message="Reference saved to library.",
    )


@router.post("/sessions", response_model=EditFlowSessionOut)
def create_session(body: EditFlowSessionCreate, db: Session = Depends(get_db)) -> EditFlowSessionOut:
    row = efs.create_edit_flow_session(
        db,
        base_image_url=body.base_image_url,
        preloaded_reference_url=body.preloaded_reference_url,
    )
    return _session_out(db, row.id)


@router.get("/sessions/{session_id}", response_model=EditFlowSessionOut)
def get_session(session_id: int, db: Session = Depends(get_db)) -> EditFlowSessionOut:
    return _session_out(db, session_id)


@router.post("/sessions/{session_id}/chat", response_model=EditFlowChatResponse)
def post_chat(session_id: int, body: EditFlowChatRequest, db: Session = Depends(get_db)) -> EditFlowChatResponse:
    try:
        assistant, phase, requested, generated = efs.post_chat_turn(
            db, session_id=session_id, user_message=body.message
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Model returned invalid JSON: {e}") from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return EditFlowChatResponse(
        assistant_message=assistant,
        phase=phase.value,
        requested_references=requested,
        generated_reference_urls=generated,
    )


@router.post("/sessions/{session_id}/references", response_model=EditFlowReferencesResponse)
def post_references(
    session_id: int,
    body: EditFlowReferencesRequest,
    db: Session = Depends(get_db),
) -> EditFlowReferencesResponse:
    urls = _normalize_ref_urls(body.urls, max_refs=2)
    try:
        s = efs.set_session_references(db, session_id=session_id, urls=urls)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return EditFlowReferencesResponse(
        reference_urls=list(s.reference_urls or []),
        phase=s.phase.value,
    )


@router.post("/sessions/{session_id}/run-edit", response_model=EditFlowRunEditResponse)
def post_run_edit(session_id: int, db: Session = Depends(get_db)) -> EditFlowRunEditResponse:
    try:
        payload = efs.run_session_image_edit(db, session_id=session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Model returned invalid JSON: {e}") from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return EditFlowRunEditResponse(
        phase="edit_completed",
        reasoning=payload["reasoning"],
        retrieved_references=payload["retrieved_references"],
        plan=payload["plan"],
        edited_image_urls=payload["edited_image_urls"],
        critique=payload.get("critique"),
        warnings=list(payload.get("warnings") or []),
        planner_reasoning_text=payload.get("planner_reasoning_text"),
    )
