from aiokafka.client import AIOKafkaClient
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness():
    """Liveness probe – returns 200 if the process is alive."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness(request: Request):
    """Readiness probe – checks PostgreSQL, Kafka, and Redis connectivity."""
    details: dict[str, str] = {}

    # Check PostgreSQL
    try:
        engine = request.app.state.engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        details["postgres"] = "ok"
    except Exception:
        details["postgres"] = "unavailable"

    # Check Kafka via metadata request
    try:
        kafka_config = request.app.state.kafka_config
        client = AIOKafkaClient(
            bootstrap_servers=kafka_config.kafka_bootstrap_servers,
        )
        await client.bootstrap()
        await client.close()
        details["kafka"] = "ok"
    except Exception:
        details["kafka"] = "unavailable"

    # Check Redis
    try:
        redis_client = request.app.state.redis_client
        await redis_client.ping()
        details["redis"] = "ok"
    except Exception:
        details["redis"] = "unavailable"

    all_ok = all(v == "ok" for v in details.values())
    status_code = 200 if all_ok else 503
    return JSONResponse(content=details, status_code=status_code)
