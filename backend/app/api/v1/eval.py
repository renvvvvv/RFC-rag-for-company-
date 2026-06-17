"""Evaluation endpoints."""
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.exceptions import NotFoundException
from app.database import get_db
from app.models.evaluation import EvaluationDataset, EvaluationTask
from app.schemas.evaluation import (
    EvaluationDatasetCreate,
    EvaluationDatasetResponse,
    EvaluationMetricsResponse,
    EvaluationTaskCreate,
    EvaluationTaskResponse,
)
from app.schemas.user import UserResponse
from app.services.evaluation_service import evaluation_service
from app.workers.eval_tasks import run_evaluation_task

router = APIRouter(tags=["evaluation"])


@router.post(
    "/evaluation/datasets",
    response_model=EvaluationDatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset(
    payload: EvaluationDatasetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Create a new evaluation dataset."""
    if not await evaluation_service.verify_kb(db, payload.kb_id):
        raise NotFoundException(f"Knowledge base {payload.kb_id} not found")

    dataset = await evaluation_service.create_dataset(
        db=db,
        kb_id=payload.kb_id,
        name=payload.name,
        questions=payload.questions,
        ground_truths=payload.ground_truths,
        created_by=current_user.id,
    )
    return dataset


@router.get(
    "/evaluation/datasets",
    response_model=List[EvaluationDatasetResponse],
)
async def list_datasets(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """List evaluation datasets."""
    return await evaluation_service.list_datasets(
        db, skip=skip, limit=limit, created_by=current_user.id
    )


@router.post(
    "/evaluation/tasks",
    response_model=EvaluationTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    payload: EvaluationTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Create and dispatch an evaluation task."""
    dataset = await evaluation_service.get_dataset(db, payload.dataset_id)
    if dataset is None:
        raise NotFoundException(f"Dataset {payload.dataset_id} not found")

    if not await evaluation_service.verify_kb(db, payload.kb_id):
        raise NotFoundException(f"Knowledge base {payload.kb_id} not found")

    task = await evaluation_service.create_task(
        db=db,
        dataset_id=payload.dataset_id,
        kb_id=payload.kb_id,
        metrics=payload.metrics,
        created_by=current_user.id,
    )

    try:
        run_evaluation_task.delay(str(task.id), str(current_user.id))
    except Exception as exc:
        # Celery dispatch failed; mark task failed and surface the error.
        await evaluation_service.update_task_status(
            db,
            task,
            "failed",
            {"error": f"Failed to dispatch evaluation task: {exc}"},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to dispatch evaluation task: {exc}",
        )

    return task


@router.get(
    "/evaluation/tasks",
    response_model=List[EvaluationTaskResponse],
)
async def list_tasks(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """List evaluation tasks."""
    return await evaluation_service.list_tasks(
        db, skip=skip, limit=limit, created_by=current_user.id
    )


@router.get(
    "/evaluation/tasks/{task_id}",
    response_model=EvaluationTaskResponse,
)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Get an evaluation task with results."""
    task = await evaluation_service.get_task(db, task_id)
    if task is None:
        raise NotFoundException(f"Evaluation task {task_id} not found")
    return task


@router.get(
    "/evaluation/metrics",
    response_model=EvaluationMetricsResponse,
)
async def list_metrics(
    current_user: UserResponse = Depends(get_current_user),
):
    """List available evaluation metrics."""
    return {"metrics": evaluation_service.available_metrics()}
