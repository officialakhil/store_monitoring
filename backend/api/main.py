from fastapi import FastAPI

from api.routers.reports import router as reports_router

PREFIX_V1 = "/api/v1"

app = FastAPI()
app.include_router(reports_router, prefix=PREFIX_V1)


# Health check endpoint
@app.get(PREFIX_V1)
async def root():
    return {"message": "Hello World"}
