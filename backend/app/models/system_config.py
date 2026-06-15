"""System-wide runtime configuration stored in PostgreSQL."""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Text

from app.database import Base


class SystemConfig(Base):
    """Key-value store for runtime model / system configuration."""

    __tablename__ = "system_config"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    key = Column(String(128), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
