from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChatSessionOut(BaseModel):
    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    status: str
    edit_sequence_number: int
    created_at: datetime
    original_image_url: Optional[str] = None
    edited_image_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ChatSessionCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)


class ProjectOut(BaseModel):
    id: int
    project_name: str
    thumbnail_url: Optional[str] = None
    status: str
    creation_date: datetime
    last_interaction_time: Optional[datetime] = None
    total_edits: int

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=255)


class ProjectListOut(BaseModel):
    projects: list[ProjectOut] = Field(default_factory=list)


class ProjectSessionsOut(BaseModel):
    project_id: int
    project_name: str
    sessions: list[ChatSessionOut] = Field(default_factory=list)
