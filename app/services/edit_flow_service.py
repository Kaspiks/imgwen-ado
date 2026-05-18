from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.edit_flow import EditFlowMessage, EditFlowPhase, EditFlowSession
from app.services import dashscope_qwen as dq
from app.workflows.image_edit_workflow import run_image_edit_workflow

REF_REQUEST_MARKER = "[[REQUEST_REFERENCES]]"

REASONING_CHAT_SYSTEM = (
    "You are a vision-language assistant helping the user plan an image edit. You can see the base image "
    "in every user message. Discuss goals, constraints, style, and feasibility. "
    "When you need the user to attach 1–2 reference images for the downstream image-edit model, "
    "end your reply with a single line containing exactly:\n"
    f"{REF_REQUEST_MARKER}\n"
    "Put that marker on its own line with nothing else on that line. "
    "Do not claim the pixels have already been edited until the pipeline runs after references."
)


def _strip_ref_marker(text: str) -> tuple[str, bool]:
    requested = REF_REQUEST_MARKER in text
    cleaned = text.replace(REF_REQUEST_MARKER, "").strip()
    return cleaned, requested


def _build_multimodal_messages(
    *,
    base_image_url: str,
    history: list[EditFlowMessage],
    new_user_text: str,
) -> list[dict]:
    messages: list[dict] = [
        {"role": "system", "content": [{"text": REASONING_CHAT_SYSTEM}]},
    ]

    for m in history:
        if m.role == "reasoning":
            continue

        if m.role == "user":
            messages.append(
                {
                    "role": "user",
                    "content": [{"image": base_image_url}, {"text": m.content}],
                }
            )

        elif m.role == "assistant":
            messages.append(
                {
                    "role": "assistant",
                    "content": [{"text": m.content}],
                }
            )

    messages.append(
        {
            "role": "user",
            "content": [{"image": base_image_url}, {"text": new_user_text}],
        }
    )

    return messages


def _transcript(messages: list[EditFlowMessage]) -> str:
    lines: list[str] = []

    for m in messages:
        if m.role == "reasoning":
            continue

        lines.append(f"{m.role.upper()}: {m.content}")

    return "\n".join(lines)


def create_edit_flow_session(db: Session, *, base_image_url: str) -> EditFlowSession:
    row = EditFlowSession(
        base_image_url=base_image_url.strip(),
        phase=EditFlowPhase.chatting,
        reference_urls=[],
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return row


def get_edit_flow_session(db: Session, session_id: int) -> Optional[EditFlowSession]:

    return db.get(EditFlowSession, session_id)


def list_session_messages(db: Session, session_id: int) -> list[EditFlowMessage]:
    q = (
        select(EditFlowMessage)
        .where(EditFlowMessage.session_id == session_id)
        .order_by(EditFlowMessage.id.asc())
    )

    return list(db.scalars(q).all())


def append_edit_flow_message(db: Session, *, session_id: int, role: str, content: str) -> EditFlowMessage:
    row = EditFlowMessage(session_id=session_id, role=role, content=content)

    db.add(row)
    db.commit()
    db.refresh(row)

    return row


def post_chat_turn(db: Session, *, session_id: int, user_message: str) -> tuple[str, EditFlowPhase, bool]:
    session = get_edit_flow_session(db, session_id)

    if session is None:
        raise KeyError("session not found")

    history = list_session_messages(db, session_id)
    reasoning_key = settings.dashscope_reasoning_key()

    if not reasoning_key:
        raise ValueError(
            "Set DASHSCOPE_API_KEY (workspace sk-ws-... for MaaS) or DASHSCOPE_REASONING_API_KEY"
        )

    msgs = _build_multimodal_messages(
        base_image_url=session.base_image_url,
        history=history,
        new_user_text=user_message.strip(),
    )

    append_edit_flow_message(db, session_id=session_id, role="user", content=user_message.strip())

    raw = dq.multimodal_chat_text(
        api_key=reasoning_key,
        base_http_api_url=settings.dashscope_reasoning_base(),
        model=settings.qwen_vision_model,
        messages=msgs,
    )

    assistant_clean, requested_refs = _strip_ref_marker(raw)
    append_edit_flow_message(db, session_id=session_id, role="assistant", content=assistant_clean)

    if requested_refs:
        session.phase = EditFlowPhase.awaiting_references
        db.add(session)
        db.commit()

    db.refresh(session)

    return assistant_clean, session.phase, requested_refs


def set_session_references(db: Session, *, session_id: int, urls: list[str]) -> EditFlowSession:
    session = get_edit_flow_session(db, session_id)

    if session is None:
        raise KeyError("session not found")

    if session.phase == EditFlowPhase.edit_completed:
        raise ValueError("Session already completed.")

    session.reference_urls = urls
    session.phase = EditFlowPhase.awaiting_references
    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def run_session_image_edit(
    db: Session,
    *,
    session_id: int,
    top_k_refs: int = 8,
    max_refs_for_edit: int = 2,
    edit_n: int = 1,
    edit_size: str = "1024*1024",
    skip_critic: bool = False,
) -> dict:

    session = get_edit_flow_session(db, session_id)

    if session is None:
        raise KeyError("session not found")
    if session.phase == EditFlowPhase.edit_completed:
        raise ValueError("Edit already ran for this session.")

    msgs = list_session_messages(db, session_id)
    transcript = _transcript(msgs)

    if not transcript.strip():
        raise ValueError("Chat is empty. Send at least one prompt before running the edit.")

    reasoning_key = settings.dashscope_reasoning_key()

    if not reasoning_key:
        raise ValueError(
            "Set DASHSCOPE_API_KEY (workspace sk-ws-... for MaaS) or DASHSCOPE_REASONING_API_KEY"
        )

    capped = transcript[:24000]

    consolidate_prompt = (
        "The user and assistant discussed how to change this image. Read the full thread and "
        "output ONE JSON object only (no markdown) with keys: scene_description (string), "
        "salient_objects (string[]), user_goal (string), constraints (string[]), retrieval_query (string). "
        "The retrieval_query should be short text good for embedding search.\n\n"
        f"--- Conversation ---\n{capped}\n--- End ---"
    )

    reasoning = dq.vision_reasoning_json(
        api_key=reasoning_key,
        base_http_api_url=settings.dashscope_reasoning_base(),
        model=settings.qwen_vision_model,
        base_image_url=session.base_image_url,
        user_prompt=consolidate_prompt,
    )

    result = run_image_edit_workflow(
        user_prompt=transcript[:12000],
        base_image_url=session.base_image_url,
        top_k_refs=top_k_refs,
        max_refs_for_edit=max_refs_for_edit,
        edit_n=edit_n,
        edit_size=edit_size,
        skip_critic=skip_critic,
        staged_reference_urls=list(session.reference_urls or []),
        reasoning_override=reasoning,
    )

    _MAX_REASONING_CHARS = 28000
    trace = (result.planner_reasoning_text or "").strip()

    if trace:
        if len(trace) > _MAX_REASONING_CHARS:
            trace = trace[:_MAX_REASONING_CHARS] + "\n\n[truncated]"

        append_edit_flow_message(db, session_id=session_id, role="reasoning", content=trace)

    final_prompt = str(result.plan.get("final_image_edit_prompt") or "")

    if len(final_prompt) > 6000:
        final_prompt = final_prompt[:6000] + "…"

    wrap = (
        "The image-edit pipeline has finished.\n\n"
        + (
            "The message above is the text planner’s reasoning trace (when returned by the Responses API).\n\n"
            if trace
            else ""
        )
        + "Prompt sent to the image-edit model:\n"
        + (final_prompt or "(none)")
        + "\n\nDoes this match what you wanted? Use the Agree or Disagree buttons under the chat, or send a follow-up message explaining what should change."
    )

    append_edit_flow_message(db, session_id=session_id, role="assistant", content=wrap)

    payload = {
        "reasoning": result.reasoning,
        "retrieved_references": result.retrieved_references,
        "plan": result.plan,
        "edited_image_urls": result.edited_image_urls,
        "critique": result.critique,
        "warnings": result.warnings,
        "planner_reasoning_text": result.planner_reasoning_text,
    }

    session.last_edit_result = payload
    session.phase = EditFlowPhase.edit_completed
    db.add(session)
    db.commit()
    db.refresh(session)

    return payload
