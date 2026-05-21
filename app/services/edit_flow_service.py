from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.chat_session import ChatSession, ChatSessionStatus
from app.models.edit_flow import EditFlowMessage, EditFlowPhase, EditFlowSession
from app.models.image import Image
from app.models.project import Project
from app.services.dashscope_qwen import DashScopeClient
from app.services.object_storage import persist as _persist_image_url, resolve_for_model
from app.workflows.image_edit_workflow import ImageEditWorkflow

logger = logging.getLogger(__name__)


class EditFlowService:
    """Business logic for the conversational image-edit flow, bound to one DB session."""

    REF_REQUEST_MARKER = "[[REQUEST_REFERENCES]]"
    GEN_REFS_MARKER = "[[GENERATE_REFERENCES]]"

    REASONING_CHAT_SYSTEM = (
        "You are a vision-language assistant helping the user plan an image edit. You can see the base image "
        "in every user message. When the user has attached reference images, they are included after the base "
        "image and labelled in the message text — you CAN see them; describe and use them when asked. "
        "Discuss goals, constraints, style, and feasibility.\n\n"
        "When you need the user to attach 1–2 reference images, end your reply with a single line containing exactly:\n"
        f"{REF_REQUEST_MARKER}\n\n"
        "When the user is undecided and would benefit from seeing concrete options, you may proactively "
        "propose 2–3 specific looks tailored to their goal and offer to generate visual references. "
        "If they accept, or if you are confident the suggestion is useful, end your reply with:\n"
        f"{GEN_REFS_MARKER}\n"
        "<one short visual prompt per line, max 3 lines>\n"
        "CRITICAL: every generated prompt must produce an ISOLATED STYLE SWATCH — absolutely NO people, "
        "NO faces, NO bodies, NO portraits, NO models wearing the item. "
        "The image-edit model is given the base image separately; if you include people in references "
        "it will substitute their face and identity, ruining the edit.\n"
        "  • For clothing edits — generate a flat-lay or studio product shot of the garment only "
        "(e.g. 'flat-lay product photo of a black Puma zip-up hoodie, white Puma logo on chest, "
        "soft fleece texture, slight worn look, studio lighting, plain background, no person, no body, no face'). "
        "Show fabric texture, logo placement, and color accurately.\n"
        "  • For hair edits — generate a close-up hair texture swatch "
        "(e.g. 'close-up of ash brown hair strands, cool muted tone, subtle lowlights, "
        "natural studio lighting, hair color swatch, macro photography, no face').\n"
        "  • For other edits — generate an isolated swatch or product shot of the relevant element only.\n"
        "Use rich descriptors for color, finish, and texture — these become style reference images for the edit.\n\n"
        "Put markers on their own line. Do not include both markers in the same reply. "
        "Do not claim the pixels have already been edited until the pipeline runs."
    )

    def __init__(self, db: Session) -> None:
        self.db = db

    @classmethod
    def _parse_chat_markers(cls, text: str) -> tuple[str, bool, list[str]]:
        """Returns (cleaned_text, requested_user_refs, generation_prompts)."""
        requested = cls.REF_REQUEST_MARKER in text
        generation_prompts: list[str] = []

        if cls.GEN_REFS_MARKER in text:
            before, _, after = text.partition(cls.GEN_REFS_MARKER)
            for line in after.splitlines():
                line = line.strip().lstrip("-*0123456789.) ").strip()
                if line and not line.startswith("[["):
                    generation_prompts.append(line)
                if len(generation_prompts) >= 3:
                    break
            text = before

        cleaned = text.replace(cls.REF_REQUEST_MARKER, "").replace(cls.GEN_REFS_MARKER, "").strip()
        return cleaned, requested, generation_prompts

    @classmethod
    def _build_multimodal_messages(
        cls,
        *,
        base_image_url: str,
        history: list[EditFlowMessage],
        new_user_text: str,
        reference_urls: list[str] | None = None,
    ) -> list[dict]:
        # Resolve persisted MinIO URLs to inline data: URIs so DashScope can read them.
        base_image_url = resolve_for_model(base_image_url)

        messages: list[dict] = [
            {"role": "system", "content": [{"text": cls.REASONING_CHAT_SYSTEM}]},
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

        refs = [
            resolve_for_model(u)
            for u in (reference_urls or [])
            if isinstance(u, str) and u.strip()
        ][:3]
        content: list[dict] = [{"image": base_image_url}, *({"image": u} for u in refs)]

        if len(refs) == 1:
            note = (
                "[Image 1 is the base photo to edit. The next image is a reference image the user "
                "attached — treat it as style/appearance guidance, not as the scene to edit.]\n\n"
            )
        elif refs:
            note = (
                f"[Image 1 is the base photo to edit. The next {len(refs)} images are reference "
                "images the user attached — treat them as style/appearance guidance, not as the "
                "scene to edit.]\n\n"
            )
        else:
            note = ""

        content.append({"text": note + new_user_text})
        messages.append({"role": "user", "content": content})

        return messages

    @staticmethod
    def _transcript(messages: list[EditFlowMessage]) -> str:
        lines: list[str] = []

        for m in messages:
            if m.role == "reasoning":
                continue

            lines.append(f"{m.role.upper()}: {m.content}")

        return "\n".join(lines)

    def create_session(
        self,
        *,
        base_image_url: str,
        preloaded_reference_url: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> EditFlowSession:
        refs: list[str] = []
        if preloaded_reference_url:
            url = preloaded_reference_url.strip()
            if url.startswith("http") or url.startswith("data:image"):
                refs.append(url)

        row = EditFlowSession(
            base_image_url=base_image_url.strip(),
            phase=EditFlowPhase.chatting,
            reference_urls=refs,
            project_id=project_id,
        )

        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)

        return row

    def get_session(self, session_id: int) -> Optional[EditFlowSession]:
        return self.db.get(EditFlowSession, session_id)

    def get_latest_for_project(self, project_id: int) -> Optional[EditFlowSession]:
        return self.db.scalars(
            select(EditFlowSession)
            .where(EditFlowSession.project_id == project_id)
            .order_by(EditFlowSession.created_at.desc())
            .limit(1)
        ).first()

    def list_for_project(self, project_id: int) -> list[EditFlowSession]:
        return list(
            self.db.scalars(
                select(EditFlowSession)
                .where(EditFlowSession.project_id == project_id)
                .order_by(EditFlowSession.created_at.desc())
            ).all()
        )

    def list_messages(self, session_id: int) -> list[EditFlowMessage]:
        q = (
            select(EditFlowMessage)
            .where(EditFlowMessage.session_id == session_id)
            .order_by(EditFlowMessage.id.asc())
        )

        return list(self.db.scalars(q).all())

    def append_message(
        self,
        *,
        session_id: int,
        role: str,
        content: str,
        reference_urls: list[str] | None = None,
    ) -> EditFlowMessage:
        refs = [u for u in (reference_urls or []) if isinstance(u, str) and u.strip()]
        row = EditFlowMessage(session_id=session_id, role=role, content=content, reference_urls=refs)

        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)

        return row

    def post_chat_turn(
        self, *, session_id: int, user_message: str
    ) -> tuple[str, EditFlowPhase, bool, list[str]]:
        session = self.get_session(session_id)

        if session is None:
            raise KeyError("session not found")

        # Once an edit has run, any further message means the user is iterating
        # (e.g. clicking Disagree). Re-open the flow so they can refine and run
        # another edit, which chains from the previous result.
        if session.phase == EditFlowPhase.edit_completed:
            session.phase = EditFlowPhase.chatting
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

        history = self.list_messages(session_id)
        reasoning_key = settings.dashscope_reasoning_key()

        if not reasoning_key:
            raise ValueError(
                "Set DASHSCOPE_API_KEY (workspace sk-ws-... for MaaS) or DASHSCOPE_REASONING_API_KEY"
            )

        msgs = self._build_multimodal_messages(
            base_image_url=session.base_image_url,
            history=history,
            new_user_text=user_message.strip(),
            reference_urls=list(session.reference_urls or []),
        )

        self.append_message(session_id=session_id, role="user", content=user_message.strip())

        reasoning_client = DashScopeClient(
            api_key=reasoning_key,
            base_http_api_url=settings.dashscope_reasoning_base(),
        )
        raw = reasoning_client.multimodal_chat_text(
            model=settings.qwen_vision_model,
            messages=msgs,
        )

        assistant_clean, requested_refs, gen_prompts = self._parse_chat_markers(raw)

        generated_urls: list[str] = []
        if gen_prompts:
            generation_client = DashScopeClient(
                api_key=settings.dashscope_generation_key(),
                base_http_api_url=settings.dashscope_generation_base(),
            )
            for p in gen_prompts:
                try:
                    urls = generation_client.generate_image_from_text(
                        model=settings.qwen_image_generation_model,
                        prompt=p,
                        n=1,
                    )
                    generated_urls.extend(urls)
                except RuntimeError as exc:
                    msg = str(exc).strip() or "image generation failed"
                    assistant_clean += f"\n\n[Could not generate reference for '{p[:60]}...': {msg}]"

            # Inline before persisting: the user picks these as references later,
            # by which time the signed OSS URLs would have expired.
            generated_urls = [_persist_image_url(u) for u in generated_urls]

        self.append_message(
            session_id=session_id,
            role="assistant",
            content=assistant_clean,
            reference_urls=generated_urls,
        )

        if requested_refs or generated_urls:
            session.phase = EditFlowPhase.awaiting_references

        if requested_refs or generated_urls:
            self.db.add(session)
            self.db.commit()

        self.db.refresh(session)

        return assistant_clean, session.phase, requested_refs, generated_urls

    def set_references(self, *, session_id: int, urls: list[str]) -> EditFlowSession:
        session = self.get_session(session_id)

        if session is None:
            raise KeyError("session not found")

        if session.phase == EditFlowPhase.edit_completed:
            raise ValueError("Session already completed.")

        session.reference_urls = urls
        session.phase = EditFlowPhase.awaiting_references
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return session

    def run_image_edit(
        self,
        *,
        session_id: int,
        top_k_refs: int = 8,
        max_refs_for_edit: int = 2,
        edit_n: int = 1,
        edit_size: str = "1024*1024",
        skip_critic: bool = False,
    ) -> dict:

        session = self.get_session(session_id)

        if session is None:
            raise KeyError("session not found")
        if session.phase == EditFlowPhase.edit_completed:
            raise ValueError("Edit already ran for this session.")

        msgs = self.list_messages(session_id)
        transcript = self._transcript(msgs)

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

        reasoning_client = DashScopeClient(
            api_key=reasoning_key,
            base_http_api_url=settings.dashscope_reasoning_base(),
        )
        reasoning = reasoning_client.vision_reasoning_json(
            model=settings.qwen_vision_model,
            base_image_url=resolve_for_model(session.base_image_url),
            user_prompt=consolidate_prompt,
        )

        result = ImageEditWorkflow().run(
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

            self.append_message(session_id=session_id, role="reasoning", content=trace)

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

        self.append_message(session_id=session_id, role="assistant", content=wrap)

        # The edit model returns short-lived signed OSS URLs. Persist them to object
        # storage once so every consumer (response payload, project history, thumbnails,
        # and the next chained edit) holds a permanent URL instead of an expiring one.
        edited_image_urls = [_persist_image_url(u) for u in result.edited_image_urls]

        payload = {
            "reasoning": result.reasoning,
            "retrieved_references": result.retrieved_references,
            "plan": result.plan,
            "edited_image_urls": edited_image_urls,
            "critique": result.critique,
            "warnings": result.warnings,
            "planner_reasoning_text": result.planner_reasoning_text,
        }

        session.last_edit_result = payload
        session.phase = EditFlowPhase.edit_completed
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        user_goal = result.reasoning.get("user_goal") if isinstance(result.reasoning, dict) else None
        try:
            self._record_relational_edit(
                edit_flow_session=session,
                edited_urls=edited_image_urls,
                final_prompt=final_prompt,
                user_goal=user_goal,
            )
        except Exception:
            logger.exception("Failed to record relational edit for session %s", session_id)
            self.db.rollback()

        if edited_image_urls:
            # Chain the (already persisted) result as the next base image.
            session.base_image_url = edited_image_urls[0]
            self.db.add(session)
            self.db.commit()

        return payload

    def _record_relational_edit(
        self,
        *,
        edit_flow_session: EditFlowSession,
        edited_urls: list[str],
        final_prompt: str,
        user_goal: Optional[str],
    ) -> Optional[ChatSession]:

        project_id = edit_flow_session.project_id
        if project_id is None:
            return None

        last_seq = self.db.scalars(
            select(ChatSession.edit_sequence_number)
            .where(ChatSession.project_id == project_id)
            .order_by(ChatSession.edit_sequence_number.desc())
            .limit(1)
        ).first()

        next_seq = int(last_seq or 0) + 1

        original_img = Image(
            filename=f"project{project_id}-seq{next_seq}-original",
            minio_bucket="external-url",
            minio_object_key=f"editflow/{edit_flow_session.id}/original",
            source_url=edit_flow_session.base_image_url,
        )

        self.db.add(original_img)
        self.db.flush()

        edited_img: Optional[Image] = None
        if edited_urls:
            edited_img = Image(
                filename=f"project{project_id}-seq{next_seq}-edited",
                minio_bucket="external-url",
                minio_object_key=f"editflow/{edit_flow_session.id}/edited-0",
                source_url=edited_urls[0],
            )
            self.db.add(edited_img)
            self.db.flush()

        title = (user_goal or final_prompt or f"Edit #{next_seq}").strip()[:255]

        chat = ChatSession(
            project_id=project_id,
            status=ChatSessionStatus.closed,
            title=title or f"Edit #{next_seq}",
            description=(final_prompt or None),
            edit_sequence_number=next_seq,
            original_image_id=original_img.id,
            edited_image_id=edited_img.id if edited_img else None,
        )


        self.db.add(chat)
        self.db.flush()

        project = self.db.get(Project, project_id)

        if project is not None:
            project.total_edits = (project.total_edits or 0) + 1
            project.last_interaction_time = func.now()

            if edited_img is not None:
                project.thumbnail_url = edited_img.source_url

            self.db.add(project)

        self.db.commit()

        return chat
