from functools import lru_cache

from fastapi import HTTPException

from app.config import settings
from app.keitaro.client import KeitaroClient


@lru_cache
def get_keitaro() -> KeitaroClient:
    if not settings.keitaro_api_key:
        raise HTTPException(
            status_code=503,
            detail="KEITARO_API_KEY не задан. Создайте .env по образцу .env.example.",
        )
    return KeitaroClient(settings.keitaro_url, settings.keitaro_api_key)


def get_keitaro_if_configured() -> KeitaroClient | None:
    if not settings.keitaro_api_key:
        return None
    return get_keitaro()