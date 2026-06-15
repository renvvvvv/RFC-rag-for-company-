"""Evaluation endpoints (placeholder)."""
from fastapi import APIRouter

router = APIRouter(tags=["eval"])


@router.get("/eval")
async def eval_overview():
    return {"message": "eval placeholder"}
