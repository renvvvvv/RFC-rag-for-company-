"""Search / retrieval endpoints (placeholder)."""
from fastapi import APIRouter

router = APIRouter(tags=["search"])


@router.post("/search")
async def search():
    return {"message": "search placeholder"}
