"""Evaluation Pydantic schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluationDatasetCreate(BaseModel):
    kb_id: UUID
    name: str
    questions: List[str] = Field(default_factory=list)
    ground_truths: List[Dict[str, Any]] = Field(default_factory=list)


class EvaluationDatasetResponse(BaseModel):
    id: UUID
    kb_id: UUID
    name: str
    questions: List[str]
    ground_truths: List[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class EvaluationTaskCreate(BaseModel):
    dataset_id: UUID
    kb_id: UUID
    metrics: Optional[List[str]] = Field(
        default_factory=lambda: [
            "recall@3",
            "mrr",
            "ndcg@3",
            "faithfulness",
            "relevance",
            "coherence",
        ]
    )


class EvaluationTaskResponse(BaseModel):
    id: UUID
    dataset_id: UUID
    kb_id: UUID
    status: str
    metrics: List[str]
    results: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvaluationMetricsResponse(BaseModel):
    metrics: List[Dict[str, Any]]
