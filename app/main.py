from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_keitaro_if_configured
from app.keitaro.client import KeitaroClient, KeitaroError
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


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    db: Session = Depends(get_db),
    client: KeitaroClient | None = Depends(get_keitaro_if_configured),
):
    stored_campaigns = db.scalars(
        select(Campaign).order_by(Campaign.created_at.desc())
    ).all()
    campaign_names: dict[int, str] = {}
    campaign_names_error = None
    if client is None:
        campaign_names_error = "KEITARO_API_KEY не задан: показаны сохранённые названия."
    else:
        try:
            campaign_names = {
                int(item["id"]): item.get("name", "")
                for item in client.list_campaigns()
            }
        except KeitaroError as exc:
            campaign_names_error = f"Не удалось обновить названия из Keitaro: {exc}"
    campaigns_list = [
        {
            "keitaro_id": campaign.keitaro_id,
            "name": campaign_names.get(campaign.keitaro_id) or campaign.name,
            "geo": campaign.geo,
            "offer_id": campaign.offer_id,
            "created_at": campaign.created_at,
        }
        for campaign in stored_campaigns
    ]
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "campaigns": campaigns_list,
            "campaign_names_error": campaign_names_error,
        },
    )


@app.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
def campaign_editor(request: Request, campaign_id: int):
    return templates.TemplateResponse(
        request=request,
        name="editor.html",
        context={"kid": campaign_id},
    )
