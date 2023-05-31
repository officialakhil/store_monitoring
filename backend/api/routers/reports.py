from datetime import datetime
from pathlib import Path
from typing import cast

from arq.jobs import Job, JobStatus
from db import AsyncSessionContextManager, StoreStatus, redis
from fastapi import APIRouter
from fastapi.responses import FileResponse
from sqlmodel import desc, select

router = APIRouter(
    prefix="/reports",
)


@router.post("/trigger_report")
async def trigger_report():
    async with AsyncSessionContextManager() as session:
        # Temporary: the current timestamp to be the max timestamp
        # among all the observations in the first CSV
        current_timestamp = (
            await session.exec(
                (
                    select(StoreStatus.timestamp_utc)
                    .order_by(desc(StoreStatus.timestamp_utc))
                    .limit(1)
                )
            )
        ).one()
        current_timestamp = cast(datetime, current_timestamp)
        # current_timestamp = datetime.utcnow().replace(tzinfo=timezone.utc)

    job = await redis.redis_pool.enqueue_job(
        "calculate_uptime_downtime_async", current_timestamp
    )
    return {"message": "Report triggered", "task_id": job.job_id}


@router.get("/get_report")
async def get_report(report_id: str):
    job = Job(report_id, redis.redis_pool)
    job_status = await job.status()

    if job_status == JobStatus.not_found:
        return {"message": "Report not found", "report_id": report_id}, 404
    elif job_status == JobStatus.queued:
        return {"message": "Report queued", "report_id": report_id}
    elif job_status == JobStatus.deferred:
        return {"message": "Report deferred", "report_id": report_id}
    elif job_status == JobStatus.in_progress:
        progress = await redis.redis_pool.json().get(f"job:{report_id}:progress")
        stores_processed, total_stores = 0, 0

        if progress:
            stores_processed, total_stores = (
                progress["stores_processed"],
                progress["total_stores"],
            )

        return {
            "message": "Report in progress",
            "report_id": report_id,
            "stores_processed": stores_processed,
            "total_stores": total_stores,
        }
    elif job_status == JobStatus.complete:
        # File response
        OUTPUT_FILE_PATH = (
            Path(__file__).parent.parent.parent / f"reports/{job.job_id}.csv"
        )

        return FileResponse(
            OUTPUT_FILE_PATH,
            media_type="text/csv",
            filename=f"{job.job_id}_stores_report.csv",
            headers={
                "message": "Report complete",
                "report_id": report_id,
            },
        )

    return {"message": "Report failed", "report_id": report_id}, 500
