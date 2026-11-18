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
