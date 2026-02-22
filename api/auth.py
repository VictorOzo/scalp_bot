from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from config.settings import (
    ADMIN_BOOTSTRAP_PASS,
    ADMIN_BOOTSTRAP_USER,
    API_COOKIE_DOMAIN,
    API_COOKIE_NAME,
    API_COOKIE_SAMESITE,
    API_COOKIE_SECURE,
    API_JWT_ALG,
    API_JWT_EXPIRES_MIN,
    API_JWT_SECRET,
)
from storage.db import connect, init_db, utc_now_iso

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str
    role: str


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    role: str


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + pad)


def hash_password(password: str, *, iterations: int = 120_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64url(salt)}${_b64url(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, iterations_raw, salt_raw, digest_raw = password_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
    except Exception:
        return False
    salt = _b64url_decode(salt_raw)
    expected = _b64url_decode(digest_raw)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def create_jwt(*, username: str, role: str) -> str:
    if API_JWT_ALG != "HS256":
        raise ValueError("Only HS256 is supported")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=API_JWT_EXPIRES_MIN)).timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(API_JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url(signature)}"


def decode_jwt(token: str) -> dict[str, object]:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(API_JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_sig = _b64url_decode(sig_b64)
    if not hmac.compare_digest(actual_sig, expected_sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")

    payload = json.loads(_b64url_decode(payload_b64))
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if int(payload.get("exp", 0)) < now_ts:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return payload


def get_current_user_from_cookie(cookie_value: str | None, conn: sqlite3.Connection) -> AuthenticatedUser:
    if not cookie_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    payload = decode_jwt(cookie_value)
    username = str(payload.get("sub") or "")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    row = conn.execute("SELECT id, username, role FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return AuthenticatedUser(id=int(row[0]), username=str(row[1]), role=str(row[2]))


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=API_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=API_COOKIE_SECURE,
        samesite=API_COOKIE_SAMESITE,
        domain=API_COOKIE_DOMAIN,
        max_age=API_JWT_EXPIRES_MIN * 60,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=API_COOKIE_NAME,
        httponly=True,
        secure=API_COOKIE_SECURE,
        samesite=API_COOKIE_SAMESITE,
        domain=API_COOKIE_DOMAIN,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response) -> LoginResponse:
    conn = connect()
    init_db(conn)
    try:
        row = conn.execute(
            "SELECT username, password_hash, role FROM users WHERE username = ?",
            (payload.username,),
        ).fetchone()
    finally:
        conn.close()

    if row is None or not verify_password(payload.password, str(row[1])):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_jwt(username=str(row[0]), role=str(row[2]))
    set_auth_cookie(response, token)
    return LoginResponse(username=str(row[0]), role=str(row[2]))


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    clear_auth_cookie(response)
    return {"ok": True}


def ensure_user(conn: sqlite3.Connection, *, username: str, password: str, role: str) -> None:
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing is not None:
        return
    conn.execute(
        "INSERT INTO users (username, password_hash, role, created_ts_utc) VALUES (?, ?, ?, ?)",
        (username, hash_password(password), role, utc_now_iso()),
    )
    conn.commit()


def bootstrap_admin_from_env() -> None:
    if not ADMIN_BOOTSTRAP_USER or not ADMIN_BOOTSTRAP_PASS:
        return
    conn = connect()
    init_db(conn)
    try:
        ensure_user(conn, username=ADMIN_BOOTSTRAP_USER, password=ADMIN_BOOTSTRAP_PASS, role="admin")
    finally:
        conn.close()
