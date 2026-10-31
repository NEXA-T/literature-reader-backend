from fastapi import APIRouter

from app.api.v1.endpoints import explain, health, generate_image

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(explain.router)
api_router.include_router(generate_image.router)