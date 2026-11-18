from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.db import SessionLocal
from app.keitaro.client import KeitaroError
from app.models import Campaign
from app.routers import campaigns, editor

ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))
app = FastAPI(title="Adrobot", description="Управление кампаниями и потоками Keitaro")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
app.include_router(campaigns.router)
app.include_router(editor.router)


@app.exception_handler(KeitaroError)
async def keitaro_error_handler(_: Request, exc: KeitaroError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/", response_class=HTMLResponse)
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


@app.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
def campaign_editor(request: Request, campaign_id: int):
    return templates.TemplateResponse(
        request=request,
        name="editor.html",
        context={"kid": campaign_id},
    )
