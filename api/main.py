from fastapi import FastAPI
from tortoise.contrib.fastapi import register_tortoise

from api.routers.reports import router as reports_router

PREFIX_V1 = "/api/v1"

app = FastAPI()
app.include_router(reports_router, prefix=PREFIX_V1)


# Health check endpoint
@app.get(PREFIX_V1)
async def root():
    return {"message": "Hello World"}


# Register Tortoise ORM
register_tortoise(
    app,
    modules={"models": ["models"]},
    db_url="postgres://akhiltulluri@localhost:5432/loop",
    generate_schemas=True,
    add_exception_handlers=True,
)
