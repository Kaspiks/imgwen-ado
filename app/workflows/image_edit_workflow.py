from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import settings
from app.services import dashscope_qwen as dq
from app.services.qdrant_reference_search import qdrant_client, reference_image_urls, search_references


@dataclass
class ImageEditWorkflowResult:
    reasoning: dict[str, Any]
    retrieved_references: list[dict[str, Any]]
    plan: dict[str, Any]
    edited_image_urls: list[str]
    critique: Optional[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
    planner_reasoning_text: Optional[str] = None


def run_image_edit_workflow(
    *,
    user_prompt: str,
    base_image_url: str,
    top_k_refs: int = 8,
    max_refs_for_edit: int = 2,
    edit_n: int = 1,
    edit_size: str = "1024*1024",
    skip_critic: bool = False,
    staged_reference_urls: Optional[list[str]] = None,
    reasoning_override: Optional[dict[str, Any]] = None,
    edit_watermark: bool = True,
    edit_negative_prompt: str = "",
) -> ImageEditWorkflowResult:
    """
    Orchestrates: vision (MultiModalConversation + qwen-vl-*) → Qdrant (text-embedding-v*) →
    text planner (OpenAI-compatible qwen3-max or native Generation) →
    qwen-image-edit-max (MultiModalConversation) → vision critic.

    ``base_image_url`` may be HTTPS or ``data:image/...;base64,...`` per DashScope docs.

    If ``reasoning_override`` is set, the initial vision JSON step is skipped (e.g. after a chat phase).
    ``staged_reference_urls`` are merged before Qdrant hits when building inputs for the image-edit model.
    """

    warnings: list[str] = []
    reasoning_key = settings.dashscope_reasoning_key()
    editing_key = settings.dashscope_editing_key()

    if not reasoning_key:
        raise ValueError(
            "Set DASHSCOPE_API_KEY or DASHSCOPE_REASONING_API_KEY for vision, embeddings, and planner "
            "(use the workspace sk-ws-... key when DASHSCOPE_BASE_HTTP_API_URL is a ws-...maas host)."
        )

    if not editing_key:
        raise ValueError("Set DASHSCOPE_API_KEY or DASHSCOPE_EDITING_API_KEY for image edit.")

    reasoning_base = settings.dashscope_reasoning_base()
    editing_base = settings.dashscope_editing_base()

    if reasoning_override is not None:
        reasoning = reasoning_override
    else:
        reasoning = dq.vision_reasoning_json(
            api_key=reasoning_key,
            base_http_api_url=reasoning_base,
            model=settings.qwen_vision_model,
            base_image_url=base_image_url,
            user_prompt=user_prompt,
        )

    retrieval_query = str(
        reasoning.get("retrieval_query")
        or reasoning.get("user_goal")
        or user_prompt
    )

    qvec = dq.embed_text(
        api_key=reasoning_key,
        base_http_api_url=reasoning_base,
        model=settings.qwen_embedding_model,
        text=retrieval_query,
        text_type="query",
    )

    qclient = qdrant_client(settings.qdrant_url)

    retrieved = search_references(
        qclient,
        collection=settings.qdrant_collection,
        query_vector=qvec,
        limit=top_k_refs,
    )

    if not retrieved:
        warnings.append(
            f"No vectors returned from Qdrant collection {settings.qdrant_collection!r} "
            "(collection missing, empty, or wrong embedding size)."
        )

    staged_raw = list(staged_reference_urls or [])

    staged: list[str] = []

    for u in staged_raw:
        if isinstance(u, str):
            u2 = u.strip()
            if (u2.startswith("http") or u2.startswith("data:image")) and u2 not in staged:
                staged.append(u2)

        if len(staged) >= max_refs_for_edit:
            break

    ref_urls = reference_image_urls(retrieved, max_refs=max_refs_for_edit)
    merged: list[str] = []

    for u in staged:
        if u not in merged:
            merged.append(u)
        if len(merged) >= max_refs_for_edit:
            break

    for u in ref_urls:
        if u not in merged and len(merged) < max_refs_for_edit:
            merged.append(u)

    ref_context = "\n".join(
        f"- {row}" for row in retrieved[: min(8, len(retrieved))]
    )

    planner_system = (
        "You are an edit planner for an image editor. Output one JSON object only, no markdown. "
        "Schema: "
        '{"final_image_edit_prompt": string, "reference_roles": string[], "notes": string}\n\n'
        "When writing final_image_edit_prompt, follow these rules:\n"
        "- Match the reference color's exact tone (cool vs warm, muted vs vivid) — do not default to warm or saturated.\n"
        "- Explicitly state 'low saturation, natural-looking' if the reference hair appears muted or sun-bleached.\n"
        "- Preserve tonal variation, highlights, and texture from the reference — avoid uniform flat color.\n"
        "- If avoiding a specific artifact (e.g. orange cast, artificial dye look), name it explicitly as something to avoid."
    )

    planner_user = (
        f"User request / dialogue context:\n{user_prompt}\n\n"
        f"Vision analysis (JSON):\n{reasoning}\n\n"
        f"User-supplied reference image URLs (may be empty):\n{chr(10).join(staged) if staged else '(none)'}\n\n"
        f"Retrieved reference rows from vector DB (may be empty):\n{ref_context or '(none)'}\n\n"
        "Write `final_image_edit_prompt` as a single clear instruction for an image-edit model. "
        "Name roles if multiple reference images are used (Image 1 = base, Image 2+ = references). "
        "Describe the target color precisely — include tone (warm/cool/neutral), saturation level (muted/natural/vivid), "
        "and any variation like highlights or roots. Mention what to avoid if the reference is subtle or natural-looking."
    )

    plan, planner_reasoning = dq.text_json_completion(
        api_key=reasoning_key,
        base_http_api_url=reasoning_base,
        model=settings.qwen_text_model,
        system=planner_system,
        user=planner_user,
    )

    final_prompt = str(plan.get("final_image_edit_prompt") or user_prompt)

    edited_urls = dq.run_image_edit(
        api_key=editing_key,
        base_http_api_url=editing_base,
        model=settings.qwen_image_edit_model,
        base_image_url=base_image_url,
        reference_image_urls=merged,
        edit_prompt=final_prompt,
        n=edit_n,
        size=edit_size,
        watermark=edit_watermark,
        negative_prompt=edit_negative_prompt,
    )

    critique: Optional[dict[str, Any]] = None

    if not skip_critic and edited_urls:
        critique = dq.critic_json(
            api_key=reasoning_key,
            base_http_api_url=reasoning_base,
            model=settings.qwen_vision_model,
            base_image_url=base_image_url,
            edited_image_url=edited_urls[0],
            user_prompt=user_prompt,
            edit_prompt=final_prompt,
        )

    return ImageEditWorkflowResult(
        reasoning=reasoning,
        retrieved_references=retrieved,
        plan=plan,
        edited_image_urls=edited_urls,
        critique=critique,
        warnings=warnings,
        planner_reasoning_text=planner_reasoning,
    )
