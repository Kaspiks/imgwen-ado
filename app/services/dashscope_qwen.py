from __future__ import annotations

import json
import re
from typing import Any, Mapping, MutableMapping, Sequence, Union

import dashscope
from dashscope import Generation, MultiModalConversation, TextEmbedding

ContentPart = Mapping[str, Any]


def configure_dashscope(api_key: str, base_http_api_url: str) -> None:
    dashscope.api_key = api_key
    dashscope.base_http_api_url = base_http_api_url.rstrip("/")


def _apply_dashscope_endpoint(api_key: str, base_http_api_url: str) -> None:
    configure_dashscope(api_key, base_http_api_url)


def _flatten_dashscope_error(resp: MutableMapping[str, Any]) -> tuple[str, str | None, str | None]:
    """
    DashScope HTTP errors often put the useful bits inside ``message`` as a nested dict or JSON string.
    Returns (human summary, inner_api_code, request_id).
    """
    top_code = resp.get("code")
    raw_msg = resp.get("message")
    request_id: str | None = None
    inner_code: str | None = None
    inner_text: str | None = None

    parsed: Any = raw_msg
    if isinstance(raw_msg, str):
        raw_st = raw_msg.strip()

        if raw_st.startswith("{"):
            try:
                parsed = json.loads(raw_st)
            except json.JSONDecodeError:
                parsed = raw_msg
        else:
            parsed = raw_msg

    if isinstance(parsed, dict):
        inner_code = parsed.get("code") if isinstance(parsed.get("code"), str) else None
        im = parsed.get("message")

        if isinstance(im, str):
            inner_text = im

        request_id = parsed.get("request_id") if isinstance(parsed.get("request_id"), str) else None

        if inner_text is None:
            inner_text = json.dumps(parsed, ensure_ascii=False)[:800]

    elif isinstance(parsed, str):
        inner_text = parsed

    else:
        inner_text = str(parsed)

    if request_id is None and isinstance(resp.get("request_id"), str):
        request_id = resp.get("request_id")

    summary_parts: list[str] = []
    if inner_text:
        summary_parts.append(inner_text)

    if inner_code and inner_text and inner_code not in inner_text:
        summary_parts.append(f"({inner_code})")

    elif inner_code and not inner_text:
        summary_parts.append(f"code={inner_code}")

    elif str(top_code) not in ("", "None", "Unknown", None) and not inner_text:
        summary_parts.append(f"code={top_code}")

    elif str(top_code) == "Unknown" and inner_code and not inner_text:
        summary_parts.append(f"code={inner_code}")

    if not summary_parts:
        summary_parts.append(str(resp)[:500])

    summary = "; ".join(summary_parts)

    return summary, inner_code or (str(top_code) if top_code else None), request_id


def _model_not_exist_hint(step: str) -> str:
    step_lower = step.lower()
    if step_lower in ("multimodal_chat", "vision_reasoning", "critic"):
        model_var = "QWEN_VISION_MODEL"
        api = "MultiModalConversation (vision / chat / critic)"

    elif step_lower == "textembedding":
        model_var = "QWEN_EMBEDDING_MODEL"
        api = "TextEmbedding"

    elif step_lower == "generation":
        model_var = "QWEN_TEXT_MODEL"
        api = "Generation (native text planner)"

    elif step_lower == "image_edit":
        model_var = "QWEN_IMAGE_EDIT_MODEL"
        api = "MultiModalConversation (image edit)"

    else:
        model_var = "QWEN_VISION_MODEL, QWEN_TEXT_MODEL, QWEN_IMAGE_EDIT_MODEL"
        api = "DashScope"

    return (
        f"This call uses {api}. On a dedicated MaaS workspace URL, model IDs must match the exact "
        f"deployment names in the Alibaba console (not necessarily the public DashScope names).\n"
        f"Set {model_var} in .env to the model id shown next to that deployment. "
        f"If the console lists a different spelling (suffix, region, or version), copy it verbatim. "
        f"Also confirm DASHSCOPE_BASE_HTTP_API_URL (or DASHSCOPE_REASONING_BASE_HTTP_API_URL / "
        f"DASHSCOPE_EDITING_BASE_HTTP_API_URL) matches the API root shown for that workspace."
    )


def _require_ok(resp: MutableMapping[str, Any], step: str) -> None:
    code = resp.get("status_code")

    if code == 200:
        return

    detail, inner_code, request_id = _flatten_dashscope_error(resp)
    lines = [f"{step} failed: HTTP status={code}"]

    if request_id:
        lines.append(f"request_id={request_id}")

    lines.append(detail)
    low = detail.lower()

    if "model not exist" in low or (inner_code or "").lower() in ("invalidparameter", "model.notfound"):
        lines.append(_model_not_exist_hint(step))

    raise RuntimeError("\n".join(lines))


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model output, allowing ```json fences."""

    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)

    if fence:
        raw = fence.group(1).strip()

    return json.loads(raw)


def _response_content_part_text(part: Any) -> str | None:
    if part is None:
        return None

    if isinstance(part, dict):
        if part.get("text") is not None:
            return str(part["text"])

        return None

    t = getattr(part, "text", None)

    if t is not None:
        return str(t)

    return None


def responses_assistant_text(response: Any) -> str:
    output = getattr(response, "output", None)
    if not output:
        raise RuntimeError("Responses API result missing output")

    chunks: list[str] = []
    for item in output:
        itype = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)

        if itype != "message":
            continue

        content = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)

        if not content:
            continue

        for part in content:
            t = _response_content_part_text(part)

            if t:
                chunks.append(t)

    if not chunks:
        types = [
            item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
            for item in output
        ]

        raise RuntimeError(
            f"Responses API: no assistant message text in output; item types={types!r}"
        )

    return "\n".join(chunks).strip()


def _reasoning_item_summaries(item: Any) -> list[str]:
    summaries = item.get("summary") if isinstance(item, dict) else getattr(item, "summary", None)

    if summaries is None:
        return []

    if isinstance(summaries, str):
        s = summaries.strip()
        return [s] if s else []

    out: list[str] = []

    for s in summaries:
        if isinstance(s, dict):
            t = s.get("text")

        else:
            t = getattr(s, "text", None)

        if t:
            out.append(str(t).strip())

    return out


def responses_reasoning_text(response: Any) -> str | None:
    output = getattr(response, "output", None)

    if not output:
        return None

    blocks: list[str] = []

    for item in output:
        itype = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)

        if itype != "reasoning":
            continue

        for t in _reasoning_item_summaries(item):
            if t:
                blocks.append(t)

    if not blocks:
        return None

    return "\n\n".join(blocks).strip()


def multimodal_user_message(
    *,
    image_urls: Sequence[str],
    text: str,
) -> dict[str, Any]:
    content: list[ContentPart] = []

    for url in image_urls:
        content.append({"image": url})

    content.append({"text": text})
    return {"role": "user", "content": content}


def multimodal_assistant_text(resp: MutableMapping[str, Any]) -> str:
    out = resp.get("output") or {}
    choices = out.get("choices") or []

    if not choices:
        raise RuntimeError("multimodal response missing output.choices")

    msg = choices[0].get("message") or {}
    content = msg.get("content")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []

        for item in content:

            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))

        if parts:
            return "\n".join(parts)

    raise RuntimeError(f"unexpected multimodal content shape: {type(content)!r}")


def multimodal_output_image_urls(resp: MutableMapping[str, Any]) -> list[str]:
    out = resp.get("output") or {}
    choices = out.get("choices") or []

    if not choices:
        return []

    msg = choices[0].get("message") or {}
    content = msg.get("content")
    urls: list[str] = []

    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("image"):
                urls.append(str(item["image"]))

    return urls


def generation_assistant_text(resp: MutableMapping[str, Any]) -> str:
    out = resp.get("output") or {}

    if out.get("text"):
        return str(out["text"])

    choices = out.get("choices") or []

    if not choices:
        raise RuntimeError("generation response missing output text/choices")

    msg = choices[0].get("message") or {}
    content = msg.get("content")

    if isinstance(content, str):
        return content

    return json.dumps(content, ensure_ascii=False)


def embed_text(
    *,
    api_key: str,
    base_http_api_url: str,
    model: str,
    text: str,
    text_type: str = "query",
) -> list[float]:
    _apply_dashscope_endpoint(api_key, base_http_api_url)
    # text-embedding-v4 (Model Studio) matches the official snippet without text_type.
    call_kw: dict[str, Any] = {"model": model, "input": text, "api_key": api_key}

    if "v4" not in model.lower():
        call_kw["text_type"] = text_type

    resp = TextEmbedding.call(**call_kw)

    _require_ok(resp, "TextEmbedding")

    output = resp.get("output") or {}

    embeddings = output.get("embeddings")

    if not embeddings:
        raise RuntimeError("embedding response missing output.embeddings")

    vec = embeddings[0].get("embedding")

    if not isinstance(vec, list):
        raise RuntimeError("embedding vector missing or wrong type")

    return [float(x) for x in vec]


def multimodal_chat_text(
    *,
    api_key: str,
    base_http_api_url: str,
    model: str,
    messages: list[dict[str, Any]],
) -> str:
    _apply_dashscope_endpoint(api_key, base_http_api_url)

    resp = MultiModalConversation.call(
        api_key=api_key,
        model=model,
        messages=messages,
    )

    _require_ok(resp, "multimodal_chat")

    return multimodal_assistant_text(resp)


def vision_reasoning_json(
    *,
    api_key: str,
    base_http_api_url: str,
    model: str,
    base_image_url: str,
    user_prompt: str,
) -> dict[str, Any]:
    _apply_dashscope_endpoint(api_key, base_http_api_url)

    system = (
        "You analyze the user's image and request. Reply with a single JSON object only, no markdown. "
        "Schema: "
        '{"scene_description": string, "salient_objects": string[], '
        '"user_goal": string, "constraints": string[], "retrieval_query": string}'
    )

    messages = [
        {"role": "system", "content": [{"text": system}]},
        multimodal_user_message(
            image_urls=[base_image_url],
            text=f"User request: {user_prompt}",
        ),
    ]

    resp = MultiModalConversation.call(
        api_key=api_key,
        model=model,
        messages=messages,
    )

    _require_ok(resp, "vision_reasoning")

    return parse_json_object(multimodal_assistant_text(resp))


def text_json_completion(
    *,
    api_key: str,
    base_http_api_url: str,
    model: str,
    system: str,
    user: str,
) -> tuple[dict[str, Any], str | None]:
    """Structured JSON via Responses API, OpenAI chat, or native Generation.

    Returns ``(parsed_json, planner_reasoning_text)``. Reasoning is only set for the
    Responses API path when the provider returns ``type=reasoning`` summary items.
    """
    from app.config import settings as app_settings

    openai_key = app_settings.dashscope_openai_key()

    responses_base = (app_settings.dashscope_openai_responses_base_url or "").strip()

    if responses_base:
        from openai import OpenAI

        client = OpenAI(api_key=openai_key, base_url=responses_base.rstrip("/"))

        create_kw: dict[str, Any] = {
            "model": model,
            "instructions": system,
            "input": user,
        }

        if app_settings.dashscope_planner_enable_thinking:
            create_kw["extra_body"] = {"enable_thinking": True}

        resp = client.responses.create(**create_kw)
        reasoning = responses_reasoning_text(resp)
        raw = responses_assistant_text(resp).strip()

        try:
            return parse_json_object(raw), reasoning

        except json.JSONDecodeError as e:

            raise RuntimeError(
                f"Responses model returned non-JSON (first 400 chars): {raw[:400]!r}"
            ) from e

    compat = (app_settings.dashscope_openai_compatible_base_url or "").strip()

    if compat:
        from openai import OpenAI

        client = OpenAI(api_key=openai_key, base_url=compat.rstrip("/"))

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )

        raw = (completion.choices[0].message.content or "").strip()

        try:
            return parse_json_object(raw), None

        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"OpenAI-compatible model returned non-JSON (first 400 chars): {raw[:400]!r}"
            ) from e

    _apply_dashscope_endpoint(api_key, base_http_api_url)

    resp = Generation.call(
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        result_format="message",
    )

    _require_ok(resp, "Generation")

    return parse_json_object(generation_assistant_text(resp)), None


def run_image_edit(
    *,
    api_key: str,
    base_http_api_url: str,
    model: str,
    base_image_url: str,
    reference_image_urls: Sequence[str],
    edit_prompt: str,
    n: int = 1,
    size: str = "1024*1024",
    watermark: bool = True,
    prompt_extend: bool = False,
    negative_prompt: str = "oversaturated, vivid, artificial hair dye, uniform flat color, orange tint, unnatural color cast",
    result_format: str = "message",
    stream: bool = False,
) -> list[str]:
    _apply_dashscope_endpoint(api_key, base_http_api_url)

    images: list[str] = [base_image_url]

    for u in reference_image_urls:
        if u and u not in images:
            images.append(u)
        if len(images) >= 3:
            break

    content: list[Union[dict[str, str], str]] = []

    for u in images:
        content.append({"image": u})

    content.append({"text": edit_prompt})
    messages = [{"role": "user", "content": content}]

    parameters: dict[str, Any] = {
        "n": n,
        "size": size,
        "watermark": watermark,
        "negative_prompt": negative_prompt,
        "prompt_extend": prompt_extend,
        "result_format": result_format,
        "stream": stream,
    }

    resp = MultiModalConversation.call(
        api_key=api_key,
        model=model,
        messages=messages,
        **parameters,
    )

    _require_ok(resp, "image_edit")

    return multimodal_output_image_urls(resp)


def critic_json(
    *,
    api_key: str,
    base_http_api_url: str,
    model: str,
    base_image_url: str,
    edited_image_url: str,
    user_prompt: str,
    edit_prompt: str,
) -> dict[str, Any]:
    _apply_dashscope_endpoint(api_key, base_http_api_url)

    system = (
        "You compare the original and edited image against the user's intent. "
        "Reply with one JSON object only, no markdown. Schema: "
        '{"pass": boolean, "score_1_to_10": number, "issues": string[], "suggested_prompt_tweak": string}'
    )

    user_text = (
        f"User request:\n{user_prompt}\n\n"
        f"Image-edit model prompt used:\n{edit_prompt}\n\n"
        "Image 1: original. Image 2: edited result."
    )

    messages = [
        {"role": "system", "content": [{"text": system}]},
        multimodal_user_message(
            image_urls=[base_image_url, edited_image_url],
            text=user_text,
        ),
    ]

    resp = MultiModalConversation.call(
        api_key=api_key,
        model=model,
        messages=messages,
    )

    _require_ok(resp, "critic")

    return parse_json_object(multimodal_assistant_text(resp))
