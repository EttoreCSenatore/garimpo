from __future__ import annotations

from collections.abc import Generator

from fastapi import Header, HTTPException, status
from sqlmodel import Session

from app.config import settings
from app.db import engine
from app.security import tokens_match


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def require_admin(x_admin_token: str | None = Header(default=None)) -> str:
    """Authenticate admin endpoints. Disabled entirely when ADMIN_TOKEN is empty."""
    if not tokens_match(x_admin_token, settings.admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
            headers={"WWW-Authenticate": "Admin-Token"},
        )
    return "admin"
