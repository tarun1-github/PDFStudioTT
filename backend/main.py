"""FastAPI application entrypoint for PDF Studio."""
from contextlib import asynccontextmanager
from fastapi import FastAPI

from backend.config import get_settings
from backend.logging_config import configure_logging
from backend.routers import admin, auth, files, governance, health, jobs, pdf_tools, shared
from backend.security.storage import ensure_storage_layout

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    ensure_storage_layout(settings.STORAGE_ROOT)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        version="1.0.0",
        description="Enterprise Team Document Publishing Platform API",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(files.router)
    app.include_router(jobs.router)
    app.include_router(pdf_tools.router)
    app.include_router(shared.router)
    app.include_router(governance.router)
    app.include_router(admin.router)
    return app


app = create_app()
