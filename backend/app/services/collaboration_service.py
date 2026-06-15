"""Collaboration business logic: comments and bookmarks."""
import uuid
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, PermissionDeniedException
from app.models.collaboration import Bookmark, Comment
from app.schemas.collaboration import BookmarkCreate, CommentCreate


class CollaborationService:
    """Service layer for comments and bookmarks."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------
    async def create_comment(
        self, data: CommentCreate, user_id: UUID
    ) -> Comment:
        """Create a new comment or reply."""
        comment = Comment(
            user_id=user_id,
            target_type=data.target_type,
            target_id=data.target_id,
            content=data.content,
            parent_id=data.parent_id,
        )
        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)
        return comment

    async def get_comment(self, comment_id: UUID) -> Comment:
        """Fetch a comment by ID, raising if not found."""
        comment = await self.db.get(Comment, comment_id)
        if comment is None:
            raise NotFoundException(f"Comment {comment_id} not found")
        return comment

    async def list_comments_by_target(
        self, target_type: str, target_id: UUID
    ) -> List[Comment]:
        """List comments for a given target, ordered by creation time."""
        result = await self.db.execute(
            select(Comment)
            .where(Comment.target_type == target_type)
            .where(Comment.target_id == target_id)
            .order_by(Comment.created_at.asc())
        )
        return list(result.scalars().all())

    async def update_comment(
        self, comment_id: UUID, user_id: UUID, content: str
    ) -> Comment:
        """Update a comment. Only the original author may edit."""
        comment = await self.get_comment(comment_id)
        if comment.user_id != user_id:
            raise PermissionDeniedException("Cannot edit another user's comment")
        comment.content = content
        await self.db.commit()
        await self.db.refresh(comment)
        return comment

    async def delete_comment(self, comment_id: UUID, user_id: UUID) -> None:
        """Delete a comment. Only the original author may delete."""
        comment = await self.get_comment(comment_id)
        if comment.user_id != user_id:
            raise PermissionDeniedException("Cannot delete another user's comment")
        await self.db.delete(comment)
        await self.db.commit()

    # ------------------------------------------------------------------
    # Bookmarks
    # ------------------------------------------------------------------
    async def create_bookmark(
        self, data: BookmarkCreate, user_id: UUID
    ) -> Bookmark:
        """Create a bookmark for the current user.

        If a bookmark already exists for the same target, return it.
        """
        existing = await self._get_bookmark_by_target(
            user_id, data.target_type, data.target_id
        )
        if existing:
            return existing

        bookmark = Bookmark(
            user_id=user_id,
            target_type=data.target_type,
            target_id=data.target_id,
            note=data.note,
        )
        self.db.add(bookmark)
        await self.db.commit()
        await self.db.refresh(bookmark)
        return bookmark

    async def get_bookmark(self, bookmark_id: UUID) -> Bookmark:
        """Fetch a bookmark by ID, raising if not found."""
        bookmark = await self.db.get(Bookmark, bookmark_id)
        if bookmark is None:
            raise NotFoundException(f"Bookmark {bookmark_id} not found")
        return bookmark

    async def list_bookmarks_for_user(self, user_id: UUID) -> List[Bookmark]:
        """List all bookmarks belonging to a user."""
        result = await self.db.execute(
            select(Bookmark)
            .where(Bookmark.user_id == user_id)
            .order_by(Bookmark.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_bookmark(self, bookmark_id: UUID, user_id: UUID) -> None:
        """Delete a bookmark. Only the owner may delete."""
        bookmark = await self.get_bookmark(bookmark_id)
        if bookmark.user_id != user_id:
            raise PermissionDeniedException("Cannot delete another user's bookmark")
        await self.db.delete(bookmark)
        await self.db.commit()

    async def _get_bookmark_by_target(
        self, user_id: UUID, target_type: str, target_id: UUID
    ) -> Optional[Bookmark]:
        result = await self.db.execute(
            select(Bookmark).where(
                Bookmark.user_id == user_id,
                Bookmark.target_type == target_type,
                Bookmark.target_id == target_id,
            )
        )
        return result.scalar_one_or_none()
