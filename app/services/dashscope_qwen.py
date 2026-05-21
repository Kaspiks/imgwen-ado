from __future__ import annotations

import json
import re
from typing import Any, Mapping, MutableMapping, Sequence, Union

import dashscope
from dashscope import Generation, ImageSynthesis, MultiModalConversation, TextEmbedding
from dashscope.common.error import DashScopeException

ContentPart = Mapping[str, Any]


class DashScopeClient:
    """Thin OOP wrapper around the DashScope SDK bound to a single endpoint.

    The DashScope SDK configures its endpoint via module globals, so every call
    re-applies this client's ``api_key`` / ``base_http_api_url`` before issuing a
    request — letting multiple clients (reasoning, editing, generation) coexist.
    """

    def __init__(self, *, api_key: str, base_http_api_url: str) -> None:
        self.api_key = api_key
        self.base_http_api_url = base_http_api_url

    def _configure(self) -> None:
        dashscope.api_key = self.api_key
        dashscope.base_http_api_url = self.base_http_api_url.rstrip("/")

    @staticmethod
    def format_sdk_error(exc: BaseException) -> str:
        """Readable message from dashscope SDK exceptions (InvalidTask, ApiException, etc.)."""
        return str(exc).strip() or type(exc).__name__

    @staticmethod
    def _flatten_error(resp: MutableMapping[str, Any]) -> tuple[str, str | None, str | None]:
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

    @staticmethod
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

        elif step_lower == "image_generation":
            model_var = "QWEN_IMAGE_GENERATION_MODEL"
            api = "ImageGeneration (wan2.5/2.6 text-to-image) or ImageSynthesis (legacy wanx)"

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

    @classmethod
    def _require_ok(cls, resp: MutableMapping[str, Any], step: str) -> None:
        code = resp.get("status_code")

        if code == 200:
            return

        detail, inner_code, request_id = cls._flatten_error(resp)
        lines = [f"{step} failed: HTTP status={code}"]

        if request_id:
            lines.append(f"request_id={request_id}")

        lines.append(detail)
        low = detail.lower()

        if "model not exist" in low or (inner_code or "").lower() in ("invalidparameter", "model.notfound"):
            lines.append(cls._model_not_exist_hint(step))

        if "url error" in low and step.lower() == "image_generation":
            lines.append(
                "wan2.5/2.6 text-to-image uses ImageGeneration on the public DashScope endpoint "
                "(https://dashscope-intl.aliyuncs.com/api/v1), not workspace MaaS URLs. "
                "Set DASHSCOPE_GENERATION_BASE_HTTP_API_URL and DASHSCOPE_GENERATION_API_KEY "
                "(or DASHSCOPE_OPENAI_API_KEY) to your intl pay-as-you-go sk-... key. "
                "Also upgrade dashscope SDK to >= 1.25.8."
            )

        if "inappropriate content" in low or (inner_code or "").lower() in ("datainspectionfailed", "content_filter"):
            lines.append(
                "DashScope's content filter rejected the request. Common causes: the edit prompt "
                "describes changes to a person's appearance (hair, skin, face), the base image "
                "contains a person, or a reference image triggered the filter. Try simplifying the "
                "prompt or removing reference images."
            )

        raise RuntimeError("\n".join(lines))

    # --- pure response parsers ----------------------------------------------------

    @staticmethod
    def parse_json_object(text: str) -> dict[str, Any]:
        """Parse a JSON object from model output, allowing ```json fences."""

        raw = text.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)

        if fence:
            raw = fence.group(1).strip()

        return json.loads(raw)

    @staticmethod
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

    @classmethod
    def responses_assistant_text(cls, response: Any) -> str:
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
                t = cls._response_content_part_text(part)

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

    @staticmethod
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

    @classmethod
    def responses_reasoning_text(cls, response: Any) -> str | None:
        output = getattr(response, "output", None)

        if not output:
            return None

        blocks: list[str] = []

        for item in output:
            itype = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)

            if itype != "reasoning":
                continue

            for t in cls._reasoning_item_summaries(item):
                if t:
                    blocks.append(t)

        if not blocks:
            return None

        return "\n\n".join(blocks).strip()

    @staticmethod
    def multimodal_user_message(*, image_urls: Sequence[str], text: str) -> dict[str, Any]:
        content: list[ContentPart] = []

        for url in image_urls:
            content.append({"image": url})

        content.append({"text": text})
        return {"role": "user", "content": content}

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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
        self,
        *,
        model: str,
        text: str,
        text_type: str = "query",
    ) -> list[float]:
        self._configure()
        call_kw: dict[str, Any] = {"model": model, "input": text, "api_key": self.api_key}

        if "v4" not in model.lower():
            call_kw["text_type"] = text_type

        resp = TextEmbedding.call(**call_kw)

        self._require_ok(resp, "TextEmbedding")

        output = resp.get("output") or {}

        embeddings = output.get("embeddings")

        if not embeddings:
            raise RuntimeError("embedding response missing output.embeddings")

        vec = embeddings[0].get("embedding")

        if not isinstance(vec, list):
            raise RuntimeError("embedding vector missing or wrong type")

        return [float(x) for x in vec]

    def multimodal_chat_text(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
    ) -> str:
        self._configure()

        try:
            resp = MultiModalConversation.call(
                api_key=self.api_key,
                model=model,
                messages=messages,
            )
        except DashScopeException as exc:
            raise RuntimeError(f"multimodal_chat failed: {self.format_sdk_error(exc)}") from exc

        self._require_ok(resp, "multimodal_chat")

        return self.multimodal_assistant_text(resp)

    def vision_reasoning_json(
        self,
        *,
        model: str,
        base_image_url: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        self._configure()

        system = (
            "You analyze the user's image and request. Reply with a single JSON object only, no markdown. "
            "Schema: "
            '{"scene_description": string, "salient_objects": string[], '
            '"user_goal": string, "constraints": string[], "retrieval_query": string}'
        )

        messages = [
            {"role": "system", "content": [{"text": system}]},
            self.multimodal_user_message(
                image_urls=[base_image_url],
                text=f"User request: {user_prompt}",
            ),
        ]

        resp = MultiModalConversation.call(
            api_key=self.api_key,
            model=model,
            messages=messages,
        )

        self._require_ok(resp, "vision_reasoning")

        return self.parse_json_object(self.multimodal_assistant_text(resp))

    def text_json_completion(
        self,
        *,
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
            from openai import OpenAI, OpenAIError

            client = OpenAI(api_key=openai_key, base_url=responses_base.rstrip("/"))

            create_kw: dict[str, Any] = {
                "model": model,
                "instructions": system,
                "input": user,
            }

            if app_settings.dashscope_planner_enable_thinking:
                create_kw["extra_body"] = {"enable_thinking": True}

            try:
                resp = client.responses.create(**create_kw)
            except OpenAIError as e:
                raise RuntimeError(f"Responses API error: {e}") from e

            reasoning = self.responses_reasoning_text(resp)
            raw = self.responses_assistant_text(resp).strip()

            try:
                return self.parse_json_object(raw), reasoning
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"Responses model returned non-JSON (first 400 chars): {raw[:400]!r}"
                ) from e

        compat = (app_settings.dashscope_openai_compatible_base_url or "").strip()

        if compat:
            from openai import OpenAI, OpenAIError

            client = OpenAI(api_key=openai_key, base_url=compat.rstrip("/"))

            try:
                completion = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
            except OpenAIError as e:
                raise RuntimeError(f"OpenAI-compatible API error: {e}") from e

            raw = (completion.choices[0].message.content or "").strip()

            try:
                return self.parse_json_object(raw), None
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"OpenAI-compatible model returned non-JSON (first 400 chars): {raw[:400]!r}"
                ) from e

        self._configure()

        resp = Generation.call(
            api_key=self.api_key,
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            result_format="message",
        )

        self._require_ok(resp, "Generation")

        return self.parse_json_object(self.generation_assistant_text(resp)), None

    @staticmethod
    def _uses_image_generation_api(model: str) -> bool:
        """Multimodal wan image models (e.g. wan2.6-image) use the messages-based
        ImageGeneration API; pure text-to-image models (wan*-t2i, legacy wanx) use ImageSynthesis."""
        m = model.lower()
        return m.startswith("wan2.") and "t2i" not in m

    def generate_image_from_text(
        self,
        *,
        model: str,
        prompt: str,
        n: int = 1,
        size: str = "1024*1024",
    ) -> list[str]:
        self._configure()

        if self._uses_image_generation_api(model):
            try:
                from dashscope.aigc.image_generation import ImageGeneration
                from dashscope.api_entities.dashscope_response import Message
            except ImportError as exc:
                raise RuntimeError(
                    "wan2.5/2.6 text-to-image requires dashscope>=1.25.8 (ImageGeneration SDK). "
                    "Run: pip install -U 'dashscope>=1.25.8'"
                ) from exc

            message = Message(role="user", content=[{"text": prompt}])
            try:
                resp = ImageGeneration.call(
                    api_key=self.api_key,
                    model=model,
                    messages=[message],
                    negative_prompt="",
                    prompt_extend=True,
                    watermark=False,
                    n=n,
                    size=size,
                )
            except DashScopeException as exc:
                raise RuntimeError(f"image_generation failed: {self.format_sdk_error(exc)}") from exc
            self._require_ok(resp, "image_generation")
            urls = self.multimodal_output_image_urls(resp)
            if urls:
                return urls
            raise RuntimeError("image_generation response missing output image URLs")

        try:
            resp = ImageSynthesis.call(
                api_key=self.api_key,
                model=model,
                prompt=prompt,
                n=n,
                size=size,
            )
        except DashScopeException as exc:
            raise RuntimeError(f"image_generation failed: {self.format_sdk_error(exc)}") from exc
        self._require_ok(resp, "image_generation")
        output = resp.get("output") or {}
        results = output.get("results") or []
        urls: list[str] = []
        for r in results:
            if isinstance(r, dict) and r.get("url"):
                urls.append(str(r["url"]))
        return urls

    def run_image_edit(
        self,
        *,
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
        self._configure()

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
            api_key=self.api_key,
            model=model,
            messages=messages,
            **parameters,
        )

        self._require_ok(resp, "image_edit")

        return self.multimodal_output_image_urls(resp)

    def critic_json(
        self,
        *,
        model: str,
        base_image_url: str,
        edited_image_url: str,
        user_prompt: str,
        edit_prompt: str,
    ) -> dict[str, Any]:
        self._configure()

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
            self.multimodal_user_message(
                image_urls=[base_image_url, edited_image_url],
                text=user_text,
            ),
        ]

        resp = MultiModalConversation.call(
            api_key=self.api_key,
            model=model,
            messages=messages,
        )

        self._require_ok(resp, "critic")

        return self.parse_json_object(self.multimodal_assistant_text(resp))
