from __future__ import annotations

from httpx import AsyncClient


async def test_healthz(client: AsyncClient):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_readyz(client: AsyncClient):
    r = await client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_metrics_endpoint(client: AsyncClient):
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert "saalis_arbitrations_total" in r.text
    assert "saalis_arbitration_duration_seconds" in r.text


async def test_health_bypasses_auth(auth_client: AsyncClient):
    """Health and metrics endpoints must never require auth."""
    for path in ("/healthz", "/readyz", "/metrics"):
        r = await auth_client.get(path)
        assert r.status_code == 200, f"{path} should not require auth"
