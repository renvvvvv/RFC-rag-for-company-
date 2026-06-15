"""Tests for user schemas and user management helpers."""
import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate, UserUpdate


def test_user_create_valid():
    user = UserCreate(
        username="alice",
        email="alice@example.com",
        password="secret",
        display_name="Alice Li",
        department="HR",
        security_level="L2",
    )
    assert user.username == "alice"
    assert user.display_name == "Alice Li"
    assert user.security_level == "L2"


def test_user_update_valid():
    update = UserUpdate(
        display_name="Bob Zhang",
        department="Engineering",
        is_active=False,
    )
    assert update.display_name == "Bob Zhang"
    assert update.is_active is False


def test_user_update_invalid_security_level():
    with pytest.raises(ValidationError):
        UserUpdate(security_level="L9")


def test_user_update_invalid_status():
    with pytest.raises(ValidationError):
        UserUpdate(status="deleted")
