from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chat_session import ChatSession
from app.models.image import Image
from app.models.project import Project
from app.models.users import Client
from app.schemas.project import (
    ChatSessionCreate,
    ChatSessionOut,
    ProjectCreate,
    ProjectListOut,
    ProjectOut,
    ProjectSessionsOut,
)

router = APIRouter(prefix="/projects", tags=["projects"])

DEMO_USER_ID = "demo"


def _ensure_demo_client(db: Session) -> Client:
    client = db.query(Client).filter(Client.user_id == DEMO_USER_ID).first()
    if client is None:
        client = Client(
            user_id=DEMO_USER_ID,
            username="demo",
            email="demo@imgwen.local",
            password_hash="!nologin",
        )
        db.add(client)
        db.flush()
    return client


@router.get("", response_model=ProjectListOut)
def list_projects(db: Session = Depends(get_db)) -> ProjectListOut:
    projects = (
        db.query(Project)
        .order_by(Project.creation_date.desc())
        .all()
    )
    return ProjectListOut(projects=[ProjectOut.model_validate(p) for p in projects])


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.query(Project).filter(Project.id == project_id).first()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectOut.model_validate(project)


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    _ensure_demo_client(db)
    project = Project(project_name=body.project_name, user_id=DEMO_USER_ID)
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate(project)


@router.get("/{project_id}/sessions", response_model=ProjectSessionsOut)
def get_project_sessions(project_id: int, db: Session = Depends(get_db)) -> ProjectSessionsOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.project_id == project_id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )

    image_ids = {
        i
        for s in sessions
        for i in (s.original_image_id, s.edited_image_id)
        if i is not None
    }

    url_by_id: dict[int, Optional[str]] = {}

    if image_ids:
        for img in db.query(Image).filter(Image.id.in_(image_ids)).all():
            url_by_id[img.id] = img.source_url

    out: list[ChatSessionOut] = []

    for s in sessions:
        out.append(
            ChatSessionOut(
                id=s.id,
                title=s.title,
                description=s.description,
                status=s.status.value,
                edit_sequence_number=s.edit_sequence_number,
                created_at=s.created_at,
                original_image_url=url_by_id.get(s.original_image_id) if s.original_image_id else None,
                edited_image_url=url_by_id.get(s.edited_image_id) if s.edited_image_id else None,
            )
        )

    return ProjectSessionsOut(
        project_id=project.id,
        project_name=project.project_name,
        sessions=out,
    )


@router.post("/{project_id}/sessions", response_model=ChatSessionOut, status_code=201)
def create_chat_session(
    project_id: int,
    body: ChatSessionCreate,
    db: Session = Depends(get_db),
) -> ChatSessionOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    session = ChatSession(
        project_id=project_id,
        title=body.title or "New session",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return ChatSessionOut.model_validate(session)
