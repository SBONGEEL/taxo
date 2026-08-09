from fastapi import APIRouter

from app.routers import auth, drivers

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(drivers.router)

__all__ = ["api_router"]
