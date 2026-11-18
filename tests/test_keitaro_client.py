import httpx

from app.keitaro.client import KeitaroClient


def test_list_groups_requests_campaign_group_type():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json=[
                {"id": 1, "name": "Campaign group", "type": "campaigns"},
                {"id": 2, "name": "Offer group", "type": "offers"},
            ],
        )

    client = KeitaroClient(
        "https://keitaro.example",
        "test-key",
        transport=httpx.MockTransport(handler),
    )
    try:
        groups = client.list_groups()
    finally:
        client.close()

    assert seen[0].url.path == "/admin_api/v1/groups"
    assert seen[0].url.params["type"] == "campaigns"
    assert groups == [{"id": 1, "name": "Campaign group", "type": "campaigns"}]


def test_list_campaigns_and_delete_campaign_use_admin_api_endpoints():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": 12, "name": "Updated campaign"}])
        return httpx.Response(204)

    client = KeitaroClient(
        "https://keitaro.example",
        "test-key",
        transport=httpx.MockTransport(handler),
    )
    try:
        campaigns = client.list_campaigns()
        client.delete_campaign(34)
    finally:
        client.close()

    assert campaigns == [{"id": 12, "name": "Updated campaign"}]
    assert seen == [
        ("GET", "/admin_api/v1/campaigns"),
        ("DELETE", "/admin_api/v1/campaigns/34"),
    ]
