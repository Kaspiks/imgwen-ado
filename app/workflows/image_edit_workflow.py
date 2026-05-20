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
    edit_negative_prompt: str = "oversaturated, vivid, orange tint, unnatural color cast, artificial dye look, skin tone change, clothing change, outfit change",
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

    # Use the vision model to extract a precise color description from each staged reference.
    # This avoids passing portrait references directly to the edit model (which causes identity drift).
    staged_color_descriptions: list[str] = []
    for i, ref_url in enumerate(merged, start=1):
        try:
            color_desc = dq.multimodal_chat_text(
                api_key=reasoning_key,
                base_http_api_url=reasoning_base,
                model=settings.qwen_vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"image": ref_url},
                            {"text": (
                                "Describe ONLY the hair color and texture in this image. "
                                "Be precise: hue family, temperature (cool/warm/neutral), "
                                "saturation (muted/natural/vivid), lightness (dark/mid/light), "
                                "and any variation (highlights, lowlights, roots). "
                                "Do not describe the person's face, skin, or identity. "
                                "Reply in 1–2 sentences."
                            )},
                        ],
                    }
                ],
            )
            staged_color_descriptions.append(f"Reference {i} color: {color_desc.strip()}")
        except Exception as exc:
            warnings.append(f"Could not extract color from reference {i}: {exc}")

    ref_color_text = "\n".join(staged_color_descriptions) if staged_color_descriptions else "(none)"

    n_refs = len(merged)
    image_roles = (
        "Image 1 is the base person (ground truth). "
        + (
            f"Image{'s' if n_refs > 1 else ''} 2{'–' + str(n_refs + 1) if n_refs > 1 else ''} "
            "are color/style references ONLY — do not copy faces, body shape, or identity from them."
            if n_refs > 0 else ""
        )
    )

    planner_system = (
        "You are an edit planner for a surgical image editor (qwen-image-edit-max). "
        "Output one JSON object only, no markdown. "
        'Schema: {"final_image_edit_prompt": string, "reference_roles": string[], "notes": string}\n\n'
        "Structure of final_image_edit_prompt — exactly two parts in this order:\n"
        f"PART 1 (identity lock, always first, verbatim): '{image_roles} "
        "Preserve the exact same person from Image 1: their facial features, face shape, expression, "
        "skin tone, pose, hairstyle shape and length, clothing, and background. Do not regenerate the person.'\n\n"
        "PART 2 (the change, one sentence, max 35 words): describe ONLY the targeted attribute "
        "(e.g. hair color). Be specific about color science:\n"
        "- exact hue family (e.g. ash brown, copper auburn, platinum, honey blonde)\n"
        "- temperature (cool / neutral / warm)\n"
        "- saturation (muted / natural / vivid)\n"
        "- lightness (dark / mid / light)\n"
        "- variation (highlights, lowlights, roots) when visible in the reference\n"
        "Match the reference color exactly when one is provided; do not default to warm or saturated tones. "
        "Name avoidances explicitly (e.g. 'avoid orange cast, avoid artificial dye look')."
    )

    planner_user = (
        f"User request / dialogue:\n{user_prompt}\n\n"
        f"Vision analysis of base image (for color context only, do not echo descriptions of the person):\n{reasoning}\n\n"
        f"Color descriptions extracted from reference images by vision model:\n{ref_color_text}\n\n"
        f"Retrieved reference styles from vector DB (may be empty):\n{ref_context or '(none)'}\n\n"
        "Build final_image_edit_prompt with PART 1 first (identity lock including image roles), "
        "then PART 2 (the precise color change informed by the extracted color descriptions above)."
    )

    plan, planner_reasoning = dq.text_json_completion(
        api_key=reasoning_key,
        base_http_api_url=reasoning_base,
        model=settings.qwen_text_model,
        system=planner_system,
        user=planner_user,
    )

    final_prompt = str(plan.get("final_image_edit_prompt") or user_prompt)

    def _do_edit(prompt: str, refs: list[str]) -> list[str]:
        return dq.run_image_edit(
            api_key=editing_key,
            base_http_api_url=editing_base,
            model=settings.qwen_image_edit_model,
            base_image_url=base_image_url,
            reference_image_urls=refs,
            edit_prompt=prompt,
            n=edit_n,
            size=edit_size,
            watermark=edit_watermark,
            negative_prompt=edit_negative_prompt,
        )

    def _try_edit(prompt: str, refs: list[str]) -> list[str] | None:
        """Returns None if the content filter fires, raises on any other error."""
        try:
            return _do_edit(prompt, refs)
        except RuntimeError as exc:
            if "inappropriate content" in str(exc).lower():
                return None
            raise RuntimeError(f"{exc}\n\nEdit prompt that was sent:\n{prompt}") from exc

    # Portrait references cause identity drift — the model blends facial features from all input images
    # regardless of prompt instructions. Color info flows through the vision-extracted text descriptions
    # above. The edit model only receives the base image to guarantee identity is preserved.
    edited_urls = _try_edit(final_prompt, [])

    if edited_urls is None:
        warnings.append("Content filter still rejected; retrying with raw user prompt.")
        edited_urls = _try_edit(user_prompt, [])

    if edited_urls is None:
        raise RuntimeError(
            f"Content filter rejected all attempts.\n"
            f"Planner prompt: {final_prompt!r}\n"
            f"User prompt: {user_prompt!r}"
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
