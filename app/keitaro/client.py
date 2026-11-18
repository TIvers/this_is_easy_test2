"""HTTP client for the Keitaro Admin API v1."""
from __future__ import annotations

from typing import Any

import httpx


class KeitaroError(Exception):
    def __init__(self, message: str, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class KeitaroClient:
    def __init__(self, base_url: str, api_key: str, *, timeout: float = 30.0, transport=None):
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + "/admin_api/v1",
            headers={"Api-Key": api_key, "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise KeitaroError(f"Keitaro недоступен: {exc}") from exc
        if response.status_code >= 400:
            raise KeitaroError(
                f"Keitaro {method} {path} -> {response.status_code}: {response.text[:500]}",
                response.status_code,
                response.text,
            )
        return response.json() if response.content else None

    def list_domains(self) -> list[dict]:
        return self._request("GET", "/domains") or []

    def list_groups(self) -> list[dict]:
        groups = self._request("GET", "/groups", params={"type": "campaigns"}) or []
        return [group for group in groups if group.get("type", "campaigns") == "campaigns"]

    def list_traffic_sources(self) -> list[dict]:
        return self._request("GET", "/traffic_sources") or []

    def list_offers(self) -> list[dict]:
        return self._request("GET", "/offers") or []

    def delete_offer(self, offer_id: int) -> None:
        self._request("DELETE", f"/offers/{offer_id}")

    def list_campaigns(self) -> list[dict]:
        return self._request("GET", "/campaigns") or []

    def create_campaign(self, payload: dict) -> dict:
        return self._request("POST", "/campaigns", json=payload)

    def delete_campaign(self, campaign_id: int) -> None:
        self._request("DELETE", f"/campaigns/{campaign_id}")

    def get_campaign(self, campaign_id: int) -> dict:
        return self._request("GET", f"/campaigns/{campaign_id}")

    def create_stream(self, payload: dict) -> dict:
        return self._request("POST", "/streams", json=payload)

    def list_streams(self, campaign_id: int) -> list[dict]:
        return self._request("GET", f"/campaigns/{campaign_id}/streams") or []

    def get_stream(self, stream_id: int) -> dict:
        return self._request("GET", f"/streams/{stream_id}")

    def update_stream(self, stream_id: int, payload: dict) -> dict:
        return self._request("PUT", f"/streams/{stream_id}", json=payload)

    def delete_stream(self, stream_id: int) -> None:
        self._request("DELETE", f"/streams/{stream_id}")

    def report_by_stream_offer(self, campaign_id: int, interval: str) -> list[dict]:
        report = self._request(
            "POST",
            "/report/build",
            json={
                "range": {"interval": interval},
                "dimensions": ["stream_id", "offer_id"],
                "measures": ["clicks", "conversions", "revenue", "cr"],
                "filters": [
                    {"name": "campaign_id", "operator": "EQUALS", "expression": campaign_id}
                ],
            },
        )
        if isinstance(report, dict):
            return report.get("rows", [])
        return report or []
