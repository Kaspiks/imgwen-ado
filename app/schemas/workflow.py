from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ImageEditWorkflowRequest(BaseModel):
    user_prompt: str = Field(..., min_length=1, description="What the user wants changed")
    base_image_url: str = Field(
        ...,
        min_length=8,
        description="Public HTTPS URL to the base image (DashScope must be able to download it)",
    )
    top_k_refs: int = Field(8, ge=1, le=50)
    max_refs_for_edit: int = Field(2, ge=0, le=2, description="Image edit API allows up to 3 images total")
    edit_n: int = Field(1, ge=1, le=6)
    edit_size: str = Field("1024*1024", description="e.g. 1024*1024, 1024*1536")
    skip_critic: bool = False
    edit_watermark: bool = Field(True, description="Official qwen-image-edit-max examples often use true")
    edit_negative_prompt: str = Field("", description="Negative prompt for the edit model. Leave empty to auto-select based on edit type.")


class ImageEditWorkflowResponse(BaseModel):
    reasoning: dict[str, Any]
    retrieved_references: list[dict[str, Any]]
    plan: dict[str, Any]
    edited_image_urls: list[str]
    critique: Optional[dict[str, Any]] = None
    warnings: list[str] = Field(default_factory=list)
    planner_reasoning_text: Optional[str] = Field(
        None,
        description="Thinking summaries from the Responses API planner, when configured",
    )
