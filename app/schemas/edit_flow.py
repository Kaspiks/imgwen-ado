from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class EditFlowSessionCreate(BaseModel):
    base_image_url: str = Field(
        ...,
        min_length=12,
        description="HTTPS URL fetchable by the model, or a data:image/...;base64,... inline image",
    )
    preloaded_reference_url: Optional[str] = Field(
        None,
        description="Optional reference image URL to pre-load into the session (e.g. from Style Exploration).",
    )
    project_id: Optional[int] = Field(None, description="Project this session belongs to.")


class EditFlowMessageOut(BaseModel):
    id: int
    role: str
    content: str
    reference_urls: list[str] = Field(
        default_factory=list,
        description="Reference images attached to this message (e.g. AI-generated options)",
    )


class EditFlowSessionOut(BaseModel):
    id: int
    phase: str
    base_image_url: str
    reference_urls: list[str]
    messages: list[EditFlowMessageOut]
    last_edit_result: Optional[dict[str, Any]] = None


class EditFlowSessionSummary(BaseModel):
    id: int
    phase: str
    base_image_url: str
    reference_urls: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    edited_image_urls: list[str] = Field(default_factory=list)
    final_prompt: Optional[str] = None
    user_goal: Optional[str] = None


class EditFlowProjectHistoryOut(BaseModel):
    project_id: int
    sessions: list[EditFlowSessionSummary] = Field(default_factory=list)


class EditFlowChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=16000)


class EditFlowChatResponse(BaseModel):
    assistant_message: str
    phase: str
    requested_references: bool = Field(
        ...,
        description="True when the model asked for reference images for the edit step",
    )
    generated_reference_urls: list[str] = Field(
        default_factory=list,
        description="Reference images the assistant generated proactively this turn",
    )


class EditFlowReferencesRequest(BaseModel):
    urls: list[str] = Field(default_factory=list, max_length=4)


class EditFlowReferencesResponse(BaseModel):
    reference_urls: list[str]
    phase: str


class EditFlowRunEditResponse(BaseModel):
    phase: str
    reasoning: dict[str, Any]
    retrieved_references: list[dict[str, Any]]
    plan: dict[str, Any]
    edited_image_urls: list[str]
    critique: Optional[dict[str, Any]] = None
    warnings: list[str] = Field(default_factory=list)
    planner_reasoning_text: Optional[str] = Field(
        None,
        description="Planner thinking trace from Responses API; also appended to session chat",
    )


class ImageUploadResponse(BaseModel):
    url: str = Field(..., description="data:image/... URL or future HTTPS URL for use as base_image_url / refs")
    content_type: str
    size_bytes: int


class ReferenceIngestRequest(BaseModel):
    image_url: str = Field(
        ...,
        min_length=8,
        description="HTTPS URL or data:image/... data URL of the reference image",
    )
    description: str = Field(
        "",
        max_length=2000,
        description="Short text describing the image style / content. "
        "If empty, the VL model will generate one automatically.",
    )
    tags: list[str] = Field(default_factory=list, max_length=20)


class ReferenceIngestResponse(BaseModel):
    point_id: str
    description: str = Field(..., description="Description that was embedded (auto-generated or provided)")
    message: str


class ReferenceLibraryItemOut(BaseModel):
    point_id: str
    image_url: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class ReferenceLibraryListOut(BaseModel):
    references: list[ReferenceLibraryItemOut] = Field(default_factory=list)
