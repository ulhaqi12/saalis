from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from saalis_sidecar.app import create_app
from saalis_sidecar.settings import Settings
from saalis_sidecar.state import build_state


def make_settings(**overrides: object) -> Settings:
    defaults = dict(
        strategy="weighted_vote",
        audit_store="sqlite",
        bearer_token="",
    )
    return Settings(**{**defaults, **overrides})  # type: ignore[arg-type]


async def make_client(settings: Settings) -> tuple[object, AsyncClient]:
    app = create_app(settings)
    # ASGITransport doesn't trigger lifespan — inject AppState directly
    app.state.app_state = build_state(settings)
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return app, client


@pytest.fixture
async def client(tmp_path):
    settings = make_settings(audit_path=str(tmp_path / "test.db"))
    app, c = await make_client(settings)
    async with c:
        yield c
    await app.state.app_state.audit_store.close()


@pytest.fixture
async def auth_client(tmp_path):
    settings = make_settings(
        audit_path=str(tmp_path / "test.db"),
        bearer_token="secret",
    )
    app, c = await make_client(settings)
    async with c:
        yield c
    await app.state.app_state.audit_store.close()


RESOLVE_BODY = {
    "question": "Should we deploy?",
    "agents": [{"name": "GPT-4o", "id": "a1", "weight": 0.8}],
    "proposals": [
        {"agent_id": "a1", "id": "p1", "content": "Yes, deploy now", "confidence": 0.9},
        {"agent_id": "a1", "id": "p2", "content": "Wait for review", "confidence": 0.6},
    ],
}
