from fastapi import APIRouter


http_router_v1 = APIRouter(prefix="/api/v1")


@http_router_v1.get("/ping")
async def ping():
    return {"status": "ok"}
