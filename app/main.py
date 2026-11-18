from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from app.auth import require_login
from app.config import settings
from app.db import SessionLocal
from app.keitaro.client import KeitaroError
from app.models import Campaign
from app.routers import auth, campaigns, editor

ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))
app = FastAPI(
    title="Adrobot",
    description="Управление кампаниями и потоками Keitaro",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie="adrobot_session",
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=settings.session_cookie_secure,
)
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
app.include_router(auth.router)
app.include_router(campaigns.router)
app.include_router(editor.router)


@app.exception_handler(KeitaroError)
async def keitaro_error_handler(_: Request, exc: KeitaroError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(require_login)])
def openapi_schema():
    return app.openapi()


@app.get("/docs", include_in_schema=False, dependencies=[Depends(require_login)])
def docs():
    return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} API")


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def home(request: Request):
    with SessionLocal() as db:
        campaigns_list = db.scalars(
            select(Campaign).order_by(Campaign.created_at.desc())
        ).all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"campaigns": campaigns_list},
    )


@app.get(
    "/campaigns/{campaign_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_login)],
)
def campaign_editor(request: Request, campaign_id: int):
    return templates.TemplateResponse(
        request=request,
        name="editor.html",
        context={"kid": campaign_id},
    )
