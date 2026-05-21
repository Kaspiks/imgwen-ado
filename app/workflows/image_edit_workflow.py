from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import settings
from app.services.dashscope_qwen import DashScopeClient
from app.services.object_storage import resolve_for_model
from app.services.qdrant_reference_search import QdrantReferenceSearch

# The text planner is an LLM: it cannot interpret an image, so a base64 data URI
# is just dead weight that blows past the gateway's input-length and request-body
# limits (InvalidParameter: input length [1, 258048]; "Exceeded limit on max bytes
# to request body : 6291456"). Strip any data: URI before it reaches the planner.
_DATA_URI_RE = re.compile(r"data:[^;,\s]+;base64,[A-Za-z0-9+/=]+")
# Generous cap on the whole planner user message; real prompts are a few KB.
_MAX_PLANNER_USER_CHARS = 100_000


def _scrub_for_planner(text: str) -> str:
    """Remove base64 data URIs from text destined for the text planner."""
    return _DATA_URI_RE.sub("[image omitted]", text)


@dataclass
class ImageEditWorkflowResult:
    reasoning: dict[str, Any]
    retrieved_references: list[dict[str, Any]]
    plan: dict[str, Any]
    edited_image_urls: list[str]
    critique: Optional[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
    planner_reasoning_text: Optional[str] = None


class ImageEditWorkflow:
    """Orchestrates the multi-step image-edit pipeline.

    vision (MultiModalConversation + qwen-vl-*) → Qdrant (text-embedding-v*) →
    text planner (OpenAI-compatible qwen3-max or native Generation) →
    qwen-image-edit-max (MultiModalConversation) → vision critic.

    Behaviour varies by detected edit type (clothing / hair / general):
    - clothing: reference images are passed to the edit model; garment-appropriate negative prompt used.
    - hair: reference images are NOT passed to the edit model (portrait refs cause face blending);
            color info flows only through the vision-extracted text descriptions.
    - general: reference images are passed to the edit model.
    """

    _CLOTHING_KEYWORDS = frozenset({
        "jacket", "hoodie", "shirt", "top", "coat", "sweater", "dress",
        "pants", "jeans", "outfit", "clothing", "wear", "garment", "sleeve",
        "vest", "pullover", "sweatshirt", "blouse", "tee", "t-shirt", "trousers",
        "shorts", "skirt", "uniform",
    })

    _HAIR_KEYWORDS = frozenset({
        "hair", "hairstyle", "haircut", "dye", "highlights", "lowlights",
        "blonde", "brunette", "redhead", "bald",
    })

    # Negative prompts tuned per edit type — clothing changes should never be penalised
    # when the user explicitly asked for a clothing replacement.
    _NEGATIVE_PROMPTS: dict[str, str] = {
        "clothing": (
            "unrealistic fabric, plastic-looking material, incorrect logo, blurry texture, "
            "skin tone change, pose change, face change, identity change, background change"
        ),

        "hair": (
            "oversaturated, vivid, orange tint, unnatural color cast, artificial dye look, "
            "skin tone change, clothing change, outfit change"
        ),

        "general": (
            "skin tone change, pose change, face change, identity change"
        ),
    }

    # Vision-model prompts for extracting a description from each reference image.
    # Hair edits: describe hair only (portrait refs are NOT passed to the edit model).
    # Clothing edits: describe the garment (product refs ARE passed to the edit model).
    _REF_DESC_PROMPTS: dict[str, str] = {
        "clothing": (
            "Describe ONLY the garment visible in this image. "
            "Be precise: garment type (hoodie, jacket, shirt, etc.), "
            "primary color (hue, lightness, saturation), fabric texture and finish, "
            "any logos or branding, and distinctive design details (pockets, zippers, print, etc.). "
            "Do not describe any person's face, skin, or identity. "
            "Reply in 2–3 sentences."
        ),

        "hair": (
            "Describe ONLY the hair color and texture in this image. "
            "Be precise: hue family, temperature (cool/warm/neutral), "
            "saturation (muted/natural/vivid), lightness (dark/mid/light), "
            "and any variation (highlights, lowlights, roots). "
            "Do not describe the person's face, skin, or identity. "
            "Reply in 1–2 sentences."
        ),

        "general": (
            "Describe the key visual element in this image most relevant for using it as a "
            "style or color reference in a photo edit. "
            "Be precise about color, texture, material, and style. Reply in 2–3 sentences."
        ),
    }

    # Identity/scene lock, tuned per edit type. Crucially this preserves everything EXCEPT the
    # attribute being changed — listing "clothing" as preserved during a clothing edit (or "hair"
    # during a hair edit) makes the model contradict itself and fall back to copying the reference.
    # Every variant explicitly preserves the background/scene so the model edits the photo rather
    # than substituting it with the reference image.
    _IDENTITY_PRESERVE: dict[str, str] = {
        "clothing": (
            "Keep the exact same person and scene from Image 1 completely unchanged: their face, "
            "facial features, expression, skin tone, hair, body pose, hands, and the ENTIRE background "
            "and setting. Change ONLY the garment on their body. Do not regenerate the person, and do NOT "
            "replace the photo with the reference image — the reference only shows which garment to put on them."
        ),
        "hair": (
            "Keep the exact same person and scene from Image 1 completely unchanged: their face, facial "
            "features, expression, skin tone, body pose, clothing, and the ENTIRE background. Change ONLY "
            "the hair. Do not regenerate the person or the scene."
        ),
        "general": (
            "Keep the exact same person and scene from Image 1 completely unchanged: their face, facial "
            "features, expression, skin tone, pose, and the ENTIRE background. Apply ONLY the requested "
            "change and nothing else. Do not regenerate the person or the scene."
        ),
    }

    _PLANNER_PART2: dict[str, str] = {
        "clothing": (
            "PART 2 (the change, 1–2 sentences, max 50 words): describe ONLY the clothing replacement. "
            "Specify garment type, exact color (hue, lightness, saturation), fabric texture, "
            "any branding/logos, and how it should fit the person. "
            "If garment reference images are provided, replicate them faithfully onto the person in Image 1. "
            "Name avoidances explicitly (e.g. 'avoid plastic look, avoid incorrect logo')."
        ),

        "hair": (
            "PART 2 (the change, one sentence, max 35 words): describe ONLY the targeted hair color change. "
            "Be specific about color science:\n"
            "- exact hue family (e.g. ash brown, copper auburn, platinum, honey blonde)\n"
            "- temperature (cool / neutral / warm)\n"
            "- saturation (muted / natural / vivid)\n"
            "- lightness (dark / mid / light)\n"
            "- variation (highlights, lowlights, roots) when visible in the reference\n"
            "Match the reference color exactly when one is provided; do not default to warm or saturated tones. "
            "Name avoidances explicitly (e.g. 'avoid orange cast, avoid artificial dye look')."
        ),

        "general": (
            "PART 2 (the change, one sentence, max 35 words): describe ONLY the targeted change precisely. "
            "Be specific about the visual properties being modified. "
            "Match the reference exactly when one is provided. "
            "Name avoidances explicitly."
        ),
    }

    def __init__(self) -> None:
        reasoning_key = settings.dashscope_reasoning_key()
        editing_key = settings.dashscope_editing_key()

        if not reasoning_key:
            raise ValueError(
                "Set DASHSCOPE_API_KEY or DASHSCOPE_REASONING_API_KEY for vision, embeddings, and planner "
                "(use the workspace sk-ws-... key when DASHSCOPE_BASE_HTTP_API_URL is a ws-...maas host)."
            )

        if not editing_key:
            raise ValueError("Set DASHSCOPE_API_KEY or DASHSCOPE_EDITING_API_KEY for image edit.")

        self.reasoning = DashScopeClient(
            api_key=reasoning_key,
            base_http_api_url=settings.dashscope_reasoning_base(),
        )
        self.editing = DashScopeClient(
            api_key=editing_key,
            base_http_api_url=settings.dashscope_editing_base(),
        )
        self.search = QdrantReferenceSearch(
            url=settings.qdrant_url,
            collection=settings.qdrant_collection,
            vector_size=settings.qwen_embedding_vector_size,
        )

    @classmethod
    def _edit_type(cls, prompt: str) -> str:
        lower = prompt.lower()
        if any(k in lower for k in cls._CLOTHING_KEYWORDS):
            return "clothing"
        if any(k in lower for k in cls._HAIR_KEYWORDS):
            return "hair"
        return "general"

    def run(
        self,
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
        # Empty string or None → auto-select a negative prompt based on the edit type.
        edit_negative_prompt: str = "",
    ) -> ImageEditWorkflowResult:
        """
        ``base_image_url`` may be HTTPS or ``data:image/...;base64,...`` per DashScope docs.

        If ``reasoning_override`` is set, the initial vision JSON step is skipped (e.g. after a chat phase).
        ``staged_reference_urls`` are merged before Qdrant hits when building inputs for the image-edit model.
        """

        warnings: list[str] = []

        # Persisted references are short MinIO URLs that Alibaba cannot fetch; resolve
        # the base image to an inline data: URI for every DashScope call below.
        base_image_url = resolve_for_model(base_image_url)

        etype = self._edit_type(user_prompt)

        # Auto-select negative prompt when the caller leaves it empty.
        if not edit_negative_prompt:
            edit_negative_prompt = self._NEGATIVE_PROMPTS[etype]

        if reasoning_override is not None:
            reasoning = reasoning_override
        else:
            reasoning = self.reasoning.vision_reasoning_json(
                model=settings.qwen_vision_model,
                base_image_url=base_image_url,
                user_prompt=user_prompt,
            )

        retrieval_query = str(
            reasoning.get("retrieval_query")
            or reasoning.get("user_goal")
            or user_prompt
        )

        qvec = self.reasoning.embed_text(
            model=settings.qwen_embedding_model,
            text=retrieval_query,
            text_type="query",
        )

        retrieved = self.search.search_references(
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

        ref_urls = QdrantReferenceSearch.reference_image_urls(retrieved, max_refs=max_refs_for_edit)
        merged: list[str] = []

        for u in staged:
            if u not in merged:
                merged.append(u)
            if len(merged) >= max_refs_for_edit:
                break

        for u in ref_urls:
            if u not in merged and len(merged) < max_refs_for_edit:
                merged.append(u)

        # Resolve persisted MinIO reference URLs to inline data: URIs for the vision
        # describer and the image-edit model (Alibaba cannot fetch local MinIO URLs).
        merged = [resolve_for_model(u) for u in merged]

        # Only feed the planner the *textual* fields of each retrieved reference.
        # The raw payload also carries `image_url`, which is frequently a base64
        # `data:image/...` URI (seeded refs and uploads are stored that way); dumping
        # those into the text prompt blows past the model's input-length limit
        # (InvalidParameter: Range of input length should be [1, 258048]).
        def _ref_summary(row: dict[str, Any]) -> str:
            parts: list[str] = []
            desc = row.get("description")
            if isinstance(desc, str) and desc.strip():
                parts.append(desc.strip())
            tags = row.get("tags")
            if isinstance(tags, list) and tags:
                parts.append("tags: " + ", ".join(str(t) for t in tags))
            score = row.get("score")
            if isinstance(score, (int, float)):
                parts.append(f"score: {score:.3f}")
            return " | ".join(parts) if parts else "(no description)"

        ref_context = "\n".join(
            f"- {_ref_summary(row)}" for row in retrieved[: min(8, len(retrieved))]
        )

        # Extract a precise description from each reference image using a prompt
        # appropriate for the edit type (garment details for clothing, hair color for hair).
        ref_desc_prompt = self._REF_DESC_PROMPTS[etype]

        staged_descriptions: list[str] = []
        for i, ref_url in enumerate(merged, start=1):
            try:
                desc = self.reasoning.multimodal_chat_text(
                    model=settings.qwen_vision_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"image": ref_url},
                                {"text": ref_desc_prompt},
                            ],
                        }
                    ],
                )
                staged_descriptions.append(f"Reference {i}: {desc.strip()}")
            except Exception as exc:
                warnings.append(f"Could not extract description from reference {i}: {exc}")

        ref_desc_text = "\n".join(staged_descriptions) if staged_descriptions else "(none)"

        # Clothing/general edits pass the reference images to the edit model so it can visually
        # replicate the garment/style; identity and scene are protected by the edit-type-aware
        # identity lock below (which preserves the background and everything except the changed
        # attribute).
        # Hair edits stay text-only: hair COLOR transfers reliably through the extracted text
        # description, whereas a reference photo carrying a face/body reintroduces identity drift.
        refs_for_edit = [] if etype == "hair" else merged

        n_refs = len(refs_for_edit)

        if etype == "clothing" and n_refs > 0:
            image_roles = (
                "Image 1 is the base photo (ground truth). "
                + (
                    f"Image{'s' if n_refs > 1 else ''} 2{'–' + str(n_refs + 1) if n_refs > 1 else ''} "
                    "are garment references — copy ONLY the garment's style, color, fabric and logo onto "
                    "the person already in Image 1. Never copy faces, body shape, identity, or background from them."
                )
            )
        elif n_refs > 0:
            image_roles = (
                "Image 1 is the base photo (ground truth). "
                f"Image{'s' if n_refs > 1 else ''} 2{'–' + str(n_refs + 1) if n_refs > 1 else ''} "
                "are color/style references ONLY — copy only the relevant color/style attribute. "
                "Never copy faces, body shape, identity, or background from them."
            )
        else:
            image_roles = "Image 1 is the base photo (ground truth)."

        identity_lock = f"{image_roles} {self._IDENTITY_PRESERVE[etype]}"

        part2_instructions = self._PLANNER_PART2[etype]

        planner_system = (
            "You are an edit planner for a surgical image editor (qwen-image-edit-max). "
            "Output one JSON object only, no markdown. "
            'Schema: {"final_image_edit_prompt": string, "reference_roles": string[], "notes": string}\n\n'
            "The image editor keeps the base photo and only changes what the prompt tells it to. "
            "Your job is to make the prompt change exactly the attribute the user asked for, while "
            "explicitly preserving the rest of the photo (person, pose, and background/scene).\n\n"
            "Structure of final_image_edit_prompt — exactly two parts in this order:\n"
            f"PART 1 (identity + scene lock, always first, verbatim): '{identity_lock}'\n\n"
            + part2_instructions
        )

        planner_user = (
            f"User request / dialogue:\n{user_prompt}\n\n"
            f"Vision analysis of base image — honor its user_goal and constraints; do not echo descriptions "
            f"of the person:\n{reasoning}\n\n"
            f"Descriptions extracted from reference images by vision model:\n{ref_desc_text}\n\n"
            f"Retrieved reference styles from vector DB (may be empty):\n{ref_context or '(none)'}\n\n"
            "Build final_image_edit_prompt with PART 1 first (identity + scene lock including image roles), "
            "then PART 2 (the precise change informed by the user goal and the extracted reference descriptions). "
            "The result must be the SAME photo with only the requested attribute changed — never a substitution "
            "of the whole image with the reference."
        )

        # Defensive: a base64 data URI can reach the planner via the transcript
        # (e.g. a user pastes one) or the vision JSON. Strip it and hard-cap the
        # message so the request never exceeds the gateway's body/input limits.
        planner_user = _scrub_for_planner(planner_user)
        if len(planner_user) > _MAX_PLANNER_USER_CHARS:
            planner_user = planner_user[:_MAX_PLANNER_USER_CHARS] + "\n\n[truncated]"
            warnings.append("Planner input was truncated to stay within the model's request-size limit.")

        plan, planner_reasoning = self.reasoning.text_json_completion(
            model=settings.qwen_text_model,
            system=planner_system,
            user=planner_user,
        )

        final_prompt = str(plan.get("final_image_edit_prompt") or user_prompt)

        def _do_edit(prompt: str, refs: list[str]) -> list[str]:
            return self.editing.run_image_edit(
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

        edited_urls = _try_edit(final_prompt, refs_for_edit)

        if edited_urls is None:
            warnings.append("Content filter still rejected; retrying with raw user prompt.")
            edited_urls = _try_edit(user_prompt, refs_for_edit)

        if edited_urls is None:
            raise RuntimeError(
                f"Content filter rejected all attempts.\n"
                f"Planner prompt: {final_prompt!r}\n"
                f"User prompt: {user_prompt!r}"
            )

        critique: Optional[dict[str, Any]] = None

        if not skip_critic and edited_urls:
            critique = self.reasoning.critic_json(
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
