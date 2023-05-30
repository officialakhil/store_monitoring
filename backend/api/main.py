from contextlib import asynccontextmanager

from api.routers.reports import router as reports_router
from db import redis
from fastapi import FastAPI

PREFIX_V1 = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await redis.create_redis_pool()
        yield
    finally:
        await redis.redis_pool.close()


app = FastAPI(lifespan=lifespan)
app.include_router(reports_router, prefix=PREFIX_V1)


# Health check endpoint
@app.get(PREFIX_V1)
async def root():
    return {"message": "Hello World"}
