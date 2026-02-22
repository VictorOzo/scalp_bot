# api/deps.py
from __future__ import annotations

import sqlite3
from collections.abc import Generator

from fastapi import Cookie, Depends, HTTPException, status

from api.auth import AuthenticatedUser, get_current_user_from_cookie
from config.settings import API_COOKIE_NAME
from storage.db import connect


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def get_current_user(
    conn: sqlite3.Connection = Depends(get_db),
    cookie_value: str | None = Cookie(default=None, alias=API_COOKIE_NAME),
) -> AuthenticatedUser:
    if not cookie_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return get_current_user_from_cookie(cookie_value, conn)


def require_viewer(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if user.role not in {"viewer", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return user


def require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user