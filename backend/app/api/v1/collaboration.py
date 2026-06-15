"""Collaboration endpoints: comments and bookmarks."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.exceptions import NotFoundException, PermissionDeniedException
from app.database import get_db
from app.schemas.collaboration import (
    BookmarkCreate,
    BookmarkResponse,
    CommentCreate,
    CommentResponse,
    CommentUpdate,
)
from app.schemas.user import UserResponse
from app.services.collaboration_service import CollaborationService

router = APIRouter(tags=["collaboration"])


async def get_collaboration_service(
    db: AsyncSession = Depends(get_db),
) -> CollaborationService:
    return CollaborationService(db)


# ------------------------------------------------------------------
# Comments
# ------------------------------------------------------------------
@router.post(
    "/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    data: CommentCreate,
    service: CollaborationService = Depends(get_collaboration_service),
    current_user: UserResponse = Depends(get_current_user),
):
    """Create a comment or reply on a document/chunk."""
    return await service.create_comment(data, current_user.id)


@router.get("/comments", response_model=List[CommentResponse])
async def list_comments(
    target_type: str = Query(..., pattern=r"^(document|chunk)$"),
    target_id: UUID = Query(...),
    service: CollaborationService = Depends(get_collaboration_service),
    current_user: UserResponse = Depends(get_current_user),
):
    """List comments for a specific document or chunk."""
    _ = current_user  # endpoint requires authentication
    return await service.list_comments_by_target(target_type, target_id)


@router.put("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: UUID,
    data: CommentUpdate,
    service: CollaborationService = Depends(get_collaboration_service),
    current_user: UserResponse = Depends(get_current_user),
):
    """Update an existing comment."""
    try:
        return await service.update_comment(
            comment_id, current_user.id, data.content
        )
    except NotFoundException:
        raise
    except PermissionDeniedException:
        raise


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: UUID,
    service: CollaborationService = Depends(get_collaboration_service),
    current_user: UserResponse = Depends(get_current_user),
):
    """Delete a comment."""
    await service.delete_comment(comment_id, current_user.id)
    return None


# ------------------------------------------------------------------
# Bookmarks
# ------------------------------------------------------------------
@router.post(
    "/bookmarks",
    response_model=BookmarkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bookmark(
    data: BookmarkCreate,
    service: CollaborationService = Depends(get_collaboration_service),
    current_user: UserResponse = Depends(get_current_user),
):
    """Bookmark a document or chunk."""
    return await service.create_bookmark(data, current_user.id)


@router.get("/bookmarks", response_model=List[BookmarkResponse])
async def list_bookmarks(
    service: CollaborationService = Depends(get_collaboration_service),
    current_user: UserResponse = Depends(get_current_user),
):
    """List bookmarks for the current user."""
    return await service.list_bookmarks_for_user(current_user.id)


@router.delete("/bookmarks/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(
    bookmark_id: UUID,
    service: CollaborationService = Depends(get_collaboration_service),
    current_user: UserResponse = Depends(get_current_user),
):
    """Delete a bookmark."""
    await service.delete_bookmark(bookmark_id, current_user.id)
    return None
