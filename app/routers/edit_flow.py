from __future__ import annotations

import base64
import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.edit_flow import (
    EditFlowChatRequest,
    EditFlowChatResponse,
    EditFlowMessageOut,
    EditFlowProjectHistoryOut,
    EditFlowReferencesRequest,
    EditFlowReferencesResponse,
    EditFlowRunEditResponse,
    EditFlowSessionCreate,
    EditFlowSessionOut,
    EditFlowSessionSummary,
    ImageUploadResponse,
    ReferenceIngestRequest,
    ReferenceIngestResponse,
    ReferenceLibraryItemOut,
    ReferenceLibraryListOut,
)
from app.services.edit_flow_service import EditFlowService
from app.services.reference_library import ReferenceLibrary

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
    service = EditFlowService(db)
    s = service.get_session(session_id)

    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = service.list_messages(session_id)

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


@router.get("/references", response_model=ReferenceLibraryListOut)
def get_reference_library() -> ReferenceLibraryListOut:
    """List all style references stored in the Qdrant library."""

    rows = ReferenceLibrary().list()
    return ReferenceLibraryListOut(
        references=[ReferenceLibraryItemOut.model_validate(row) for row in rows],
    )


@router.post("/references/ingest", response_model=ReferenceIngestResponse)
def post_ingest_reference(body: ReferenceIngestRequest) -> ReferenceIngestResponse:
    """Embed a reference image into Qdrant for future retrieval and Style Exploration."""

    try:
        row = ReferenceLibrary().ingest(
            image_url=body.image_url,
            description=body.description,
            tags=list(body.tags),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Qdrant upsert failed: {exc}") from exc

    return ReferenceIngestResponse(
        point_id=row["point_id"],
        description=row["description"],
        message="Reference saved to library.",
    )


@router.get("/sessions", response_model=EditFlowSessionOut)
def get_latest_project_session(
    project_id: int = Query(..., description="Return the most recent session for this project"),
    db: Session = Depends(get_db),
) -> EditFlowSessionOut:
    session = EditFlowService(db).get_latest_for_project(project_id)
    if session is None:
        raise HTTPException(status_code=404, detail="No sessions found for this project")
    return _session_out(db, session.id)


@router.get("/project-history", response_model=EditFlowProjectHistoryOut)
def get_project_history(
    project_id: int = Query(..., description="List all edit sessions for this project, newest first"),
    db: Session = Depends(get_db),
) -> EditFlowProjectHistoryOut:
    sessions = EditFlowService(db).list_for_project(project_id)

    summaries: list[EditFlowSessionSummary] = []
    for s in sessions:
        result = s.last_edit_result or {}
        edited = result.get("edited_image_urls") or []
        plan = result.get("plan") or {}
        reasoning = result.get("reasoning") or {}
        summaries.append(
            EditFlowSessionSummary(
                id=s.id,
                phase=s.phase.value,
                base_image_url=s.base_image_url,
                reference_urls=list(s.reference_urls or []),
                created_at=s.created_at,
                updated_at=s.updated_at,
                edited_image_urls=[u for u in edited if isinstance(u, str)],
                final_prompt=(plan.get("final_image_edit_prompt") if isinstance(plan, dict) else None),
                user_goal=(reasoning.get("user_goal") if isinstance(reasoning, dict) else None),
            )
        )

    return EditFlowProjectHistoryOut(project_id=project_id, sessions=summaries)


@router.post("/sessions", response_model=EditFlowSessionOut)
def create_session(body: EditFlowSessionCreate, db: Session = Depends(get_db)) -> EditFlowSessionOut:
    row = EditFlowService(db).create_session(
        base_image_url=body.base_image_url,
        preloaded_reference_url=body.preloaded_reference_url,
        project_id=body.project_id,
    )

    return _session_out(db, row.id)


@router.get("/sessions/{session_id}", response_model=EditFlowSessionOut)
def get_session(session_id: int, db: Session = Depends(get_db)) -> EditFlowSessionOut:
    return _session_out(db, session_id)


@router.post("/sessions/{session_id}/chat", response_model=EditFlowChatResponse)
def post_chat(session_id: int, body: EditFlowChatRequest, db: Session = Depends(get_db)) -> EditFlowChatResponse:
    try:
        assistant, phase, requested, generated = EditFlowService(db).post_chat_turn(
            session_id=session_id, user_message=body.message
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
        s = EditFlowService(db).set_references(session_id=session_id, urls=urls)
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
        payload = EditFlowService(db).run_image_edit(session_id=session_id)
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
