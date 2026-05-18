from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    database_url: str = "postgresql+psycopg://app:app@127.0.0.1:5432/app_db"

    # Alibaba Cloud Model Studio / MaaS — DashScope-compatible HTTP API root (.../api/v1)
    dashscope_api_key: str = ""
    # Optional: separate keys for reasoning (VL, embeddings, planner) vs image-edit model
    dashscope_reasoning_api_key: str = ""
    dashscope_editing_api_key: str = ""
    dashscope_base_http_api_url: str = "https://dashscope-intl.aliyuncs.com/api/v1"
    # Optional: different gateways for VL+text vs image-edit (empty = use dashscope_base_http_api_url)
    dashscope_reasoning_base_http_api_url: str = ""
    dashscope_editing_base_http_api_url: str = ""

    # Optional: OpenAI-compatible base URL for text chat (qwen3-max etc.), e.g.
    # https://dashscope-intl.aliyuncs.com/compatible-mode/v1
    # When empty, text JSON uses native DashScope Generation on dashscope_base_http_api_url.
    dashscope_openai_compatible_base_url: str = ""

    # Optional: OpenAI-compatible Responses API (qwen3-max + thinking). When set, the planner
    # uses client.responses.create (see Alibaba v2 protocols URL); overrides chat completions below.
    # e.g. https://dashscope-intl.aliyuncs.com/api/v2/apps/protocols/compatible-mode/v1
    dashscope_openai_responses_base_url: str = ""
    # Passed as extra_body.enable_thinking on Responses.create when true.
    dashscope_planner_enable_thinking: bool = False

    # Optional: intl pay-as-you-go key for OpenAI-compatible / Responses planner only.
    # Use when DASHSCOPE_BASE_HTTP_API_URL is a workspace MaaS host (sk-ws-...) but the planner uses
    # DASHSCOPE_OPENAI_COMPATIBLE_BASE_URL on dashscope-intl (sk-... pay-as-you-go key).
    dashscope_openai_api_key: str = ""

    # Vision (MultiModalConversation), text planner, embeddings, critic
    qwen_vision_model: str = "qwen-vl-max"
    qwen_text_model: str = "qwen3-max"
    qwen_image_edit_model: str = "qwen-image-edit-max"

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "style_refs"
    qwen_embedding_model: str = "text-embedding-v4"
    # Vector size must match the embedding model output dimensions.
    # text-embedding-v4 → 1024, text-embedding-v2 → 1536
    qwen_embedding_vector_size: int = 1024

    def dashscope_reasoning_base(self) -> str:
        """VL reasoning, text planner, embeddings, critic (multimodal analysis)."""
        return self.dashscope_reasoning_base_http_api_url or self.dashscope_base_http_api_url

    def dashscope_editing_base(self) -> str:
        """Image edit / multimodal generation for edited pixels."""
        return self.dashscope_editing_base_http_api_url or self.dashscope_base_http_api_url

    def dashscope_reasoning_key(self) -> str:
        """API key for VL, embeddings, text planner, critic."""
        return self.dashscope_reasoning_api_key or self.dashscope_api_key

    def dashscope_editing_key(self) -> str:
        """API key for image-edit multimodal calls."""
        return self.dashscope_editing_api_key or self.dashscope_api_key

    def dashscope_openai_key(self) -> str:
        """API key for OpenAI SDK calls to intl compatible-mode / Responses URLs."""

        o = (self.dashscope_openai_api_key or "").strip()

        if o:
            return o
        return self.dashscope_reasoning_key()


settings = Settings()
