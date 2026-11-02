import httpx
import pytest
import respx

from corridor.domain.alerts import AlertCategory, AlertSeverity
from corridor.domain.geometry import LatLon
from corridor.integrations.nws import NwsAlertsClient, parse_alert
from corridor.planning.errors import UpstreamServiceError

BASE = "https://nws.test"
RAPID_CITY = LatLon(44.08, -103.23)
CALGARY = LatLon(51.05, -114.07)

HIGH_WIND = {
    "id": "urn:oid:1",
    "event": "High Wind Warning",
    "severity": "Severe",
    "status": "Actual",
    "messageType": "Alert",
    "headline": "High Wind Warning until November 3 at 6:00AM MST",
    "areaDesc": "Rapid City; Custer Co Plains",
    "onset": "2026-11-02T09:00:00-07:00",
    "ends": "2026-11-03T06:00:00-07:00",
    "expires": "2026-11-02T12:00:00-07:00",
}


def feature_collection(*props: dict[str, object]) -> dict[str, object]:
    return {"type": "FeatureCollection", "features": [{"properties": p} for p in props]}


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http:
        yield NwsAlertsClient(http, base_url=BASE)


def test_parses_cap_properties() -> None:
    alert = parse_alert(HIGH_WIND)

    assert alert is not None
    assert alert.category is AlertCategory.WIND
    assert alert.severity is AlertSeverity.SEVERE
    assert alert.starts is not None
    assert alert.starts.isoformat() == "2026-11-02T09:00:00-07:00"
    # The hazard end, not the message expiry.
    assert alert.ends is not None
    assert alert.ends.isoformat() == "2026-11-03T06:00:00-07:00"


@pytest.mark.parametrize(
    "changes",
    [{"event": "Rip Current Statement"}, {"messageType": "Cancel"}],
)
def test_ignores_off_road_and_cancelled_alerts(changes: dict[str, str]) -> None:
    assert parse_alert(HIGH_WIND | changes) is None


@respx.mock
async def test_points_outside_coverage_have_no_alerts(client: NwsAlertsClient) -> None:
    route = respx.get(f"{BASE}/alerts/active")
    route.side_effect = lambda request: (
        httpx.Response(400, json={"title": "Bad Request"})
        if request.url.params["point"].startswith("51.")
        else httpx.Response(200, json=feature_collection(HIGH_WIND))
    )

    result = await client.active_alerts([RAPID_CITY, CALGARY])

    assert [a.event for a in result[RAPID_CITY]] == ["High Wind Warning"]
    assert result[CALGARY] == ()


@respx.mock
async def test_total_failure_raises(client: NwsAlertsClient) -> None:
    respx.get(f"{BASE}/alerts/active").respond(403)
    with pytest.raises(UpstreamServiceError):
        await client.active_alerts([RAPID_CITY])
