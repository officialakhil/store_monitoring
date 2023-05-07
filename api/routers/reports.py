from fastapi import APIRouter

router = APIRouter(
    prefix="/reports",
)


@router.post("/trigger_report")
async def trigger_report():
    return {"message": "Report triggered"}


@router.get("/get_report")
async def get_report():
    return {"message": "Report generated"}
