import csv
import os.path
import sys
import typing
from pathlib import Path
import asyncio

from dateutil.parser import parse
from datetime import datetime
from sqlmodel import SQLModel, delete, insert
from sqlmodel.ext.asyncio.session import AsyncSession

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))  # For import db to work

from backend.db import (  # noqa: E402
    Store,
    StoreBusinessHours,
    StoreStatus,
    AsyncSessionContextManager,
    create_tables,
)


async def seed():
    await create_tables()
    async with AsyncSessionContextManager() as session:
        await seed_stores(session)
        await seed_store_business_hours(session)
        await seed_store_status(session)


async def seed_stores(session: AsyncSession):
    print("Seeding stores...")
    await seed_csv(
        session,
        Path(__file__).parent.parent / "data/store_timezones.csv",
        Store,
        csv_map={
            "store_id": lambda rows: int(rows[0]),
            "timezone_str": lambda rows: rows[1],
        },
    )


async def seed_store_business_hours(session: AsyncSession):
    print("Seeding store business hours...")
    await seed_csv(
        session,
        Path(__file__).parent.parent / "data/store_business_hours.csv",
        StoreBusinessHours,
        csv_map={
            "store_id": lambda rows: int(rows[0]),
            "day_of_week": lambda rows: int(rows[1]),
            "start_time_local": lambda rows: datetime.strptime(
                rows[2], "%H:%M:%S"
            ).time(),
            "end_time_local": lambda rows: datetime.strptime(
                rows[3], "%H:%M:%S"
            ).time(),
        },
    )


async def seed_store_status(session: AsyncSession):
    print("Seeding store status...")
    await seed_csv(
        session,
        Path(__file__).parent.parent / "data/store_status.csv",
        StoreStatus,
        csv_map={
            "store_id": lambda rows: int(rows[0]),
            "timestamp_utc": lambda rows: parse(rows[2]),
            "status": lambda rows: rows[1].upper(),
        },
    )


async def seed_csv(
    session: AsyncSession,
    path: Path,
    model: typing.Type[SQLModel],
    *,
    csv_map: dict[str, typing.Callable[[list[str]], typing.Any]],
    chunk_size: int = 5000,
):
    # Delete all existing rows
    delete_statement = delete(model)
    await session.exec(delete_statement)
    await session.commit()

    with path.open("r") as f:
        csv_reader = csv.reader(f)
        next(csv_reader)  # Skip header

        rows: list[SQLModel] = []

        for row in csv_reader:
            kwargs = {arg: getter(row) for arg, getter in csv_map.items()}
            rows.append(kwargs)

            if len(rows) == chunk_size:
                # This takes too long (> 18 mins for 1.8M rows and chunk size 1000)
                # session.add_all(rows)
                await session.exec(insert(model), rows)  # This takes ~3 mins
                await session.commit()
                rows = []

        if len(rows) > 0:
            await session.exec(insert(model), rows)
            await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
