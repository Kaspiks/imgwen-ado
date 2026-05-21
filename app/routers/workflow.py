from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.models.users import Client
from app.schemas.workflow import ImageEditWorkflowRequest, ImageEditWorkflowResponse
from app.workflows.image_edit_workflow import ImageEditWorkflow

router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.post("/image-edit", response_model=ImageEditWorkflowResponse)
def post_image_edit_workflow(
    body: ImageEditWorkflowRequest,
    _current_user: Client = Depends(get_current_user),
) -> ImageEditWorkflowResponse:
    try:
        result = ImageEditWorkflow().run(
            user_prompt=body.user_prompt,
            base_image_url=body.base_image_url,
            top_k_refs=body.top_k_refs,
            max_refs_for_edit=body.max_refs_for_edit,
            edit_n=body.edit_n,
            edit_size=body.edit_size,
            skip_critic=body.skip_critic,
            edit_watermark=body.edit_watermark,
            edit_negative_prompt=body.edit_negative_prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Model returned invalid JSON: {e}") from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return ImageEditWorkflowResponse(
        reasoning=result.reasoning,
        retrieved_references=result.retrieved_references,
        plan=result.plan,
        edited_image_urls=result.edited_image_urls,
        critique=result.critique,
        warnings=result.warnings,
        planner_reasoning_text=result.planner_reasoning_text,
    )
