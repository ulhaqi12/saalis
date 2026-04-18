from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from saalis_sidecar.routes import audit, human, resolve
from saalis_sidecar.settings import Settings
from saalis_sidecar.state import AppState, build_state


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    app.state.app_state = build_state(settings)
    yield
    await app.state.app_state.audit_store.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="saalis-sidecar", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings or Settings()

    @app.middleware("http")
    async def bearer_auth(request: Request, call_next: object) -> Response:
        token: str = app.state.settings.bearer_token
        if token and request.url.path not in ("/healthz", "/readyz", "/metrics"):
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {token}":
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)  # type: ignore[misc]

    app.include_router(resolve.router, prefix="/v1")
    app.include_router(audit.router, prefix="/v1")
    app.include_router(human.router, prefix="/v1")

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz(request: Request) -> dict[str, str]:
        state: AppState = request.app.state.app_state
        # Probe DB by ensuring schema is initialised
        await state.audit_store._ensure_schema()
        return {"status": "ok"}

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
