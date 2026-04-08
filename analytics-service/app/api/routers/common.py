from fastapi import APIRouter
from app.api.routers.analytics import router as analytics_router

http_router_v1 = APIRouter(prefix="/api/v1")


http_router_v1.include_router(analytics_router)


@http_router_v1.get("/ping")
async def ping():
    return {"status": "ok"}
