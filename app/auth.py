import hmac
from urllib.parse import quote

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, Request

from app.config import settings

_password_hasher = PasswordHasher()


def verify_admin_login(username: str, password: str) -> bool:
    if not settings.admin_username or not settings.admin_password_hash:
        raise HTTPException(
            status_code=503,
            detail="Вход не настроен: задайте ADMIN_USERNAME и ADMIN_PASSWORD_HASH.",
        )
    try:
        password_matches = _password_hasher.verify(settings.admin_password_hash, password)
    except (VerificationError, InvalidHashError):
        password_matches = False
    return hmac.compare_digest(username, settings.admin_username) and password_matches


def require_login(request: Request) -> None:
    if request.session.get("username") == settings.admin_username and settings.admin_username:
        return
    if request.url.path.startswith("/api/"):
        raise HTTPException(status_code=401, detail="Требуется вход")
    next_path = quote(request.url.path, safe="/")
    raise HTTPException(
        status_code=303,
        headers={"Location": f"/login?next={next_path}"},
    )
