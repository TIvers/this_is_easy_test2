from urllib.parse import urlsplit
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from app.auth import require_login, verify_admin_login
from app.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)
    next: str = "/"


def _safe_next(value: str) -> str:
    parsed = urlsplit(value)
    if (
        not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or parsed.scheme
        or parsed.netloc
    ):
        return "/"
    return value


@router.get("/login")
def login_page(request: Request, next: str = "/"):
    if request.session.get("username") == settings.admin_username and settings.admin_username:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"next_url": _safe_next(next)},
    )


@router.post("/login")
def login(body: LoginIn, request: Request):
    if not verify_admin_login(body.username, body.password):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    request.session.clear()
    request.session["username"] = body.username
    return {"ok": True, "next": _safe_next(body.next)}


@router.post("/logout", dependencies=[Depends(require_login)])
def logout(request: Request):
    request.session.clear()
    return {"ok": True}
