from contextlib import asynccontextmanager

from api.routers.reports import router as reports_router
from db import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

PREFIX_V1 = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await redis.create_redis_pool()
        yield
    finally:
        await redis.redis_pool.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"]
)  # TODO: Change this to the frontend URL
app.include_router(reports_router, prefix=PREFIX_V1)


# Health check endpoint
@app.get(PREFIX_V1)
async def root():
    return {"message": "Hello World"}
