from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging_middleware import log_requests

app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.debug)
app.middleware("http")(log_requests)
app.include_router(api_router, prefix="/api/v1")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}