import csv
import os.path
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from dateutil.parser import parse
from tortoise import Tortoise, models, run_async

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from models import Store, StoreBusinessHours, StoreStatus  # noqa: E402


async def seed():
    await Tortoise.init(
        db_url="postgres://akhiltulluri@localhost:5432/loop",
        modules={"models": ["models"]},
    )
    await Tortoise.generate_schemas()
    await seed_stores()
    await seed_store_business_hours()
    await seed_store_status()


async def seed_stores():
    print("Seeding stores...")
    await seed_csv(
        Path(__file__).parent.parent / "data/store_timezones.csv",
        Store,
        csv_map={
            "store_id": lambda rows: int(rows[0]),
            "timezone_str": lambda rows: rows[1],
        },
    )


async def seed_store_business_hours():
    print("Seeding store business hours...")
    await seed_csv(
        Path(__file__).parent.parent / "data/store_business_hours.csv",
        StoreBusinessHours,
        csv_map={
            "store_id": lambda rows: int(rows[0]),
            "day_of_week": lambda rows: int(rows[1]),
            "start_time_local": lambda rows: rows[2],
            "end_time_local": lambda rows: rows[3],
        },
    )


async def seed_store_status():
    print("Seeding store status...")
    await seed_csv(
        Path(__file__).parent.parent / "data/store_status.csv",
        StoreStatus,
        csv_map={
            "store_id": lambda rows: int(rows[0]),
            "timestamp_utc": lambda rows: parse(rows[2]),
            "status": lambda rows: rows[1].upper(),
        },
    )


async def seed_csv(
    path: Path,
    model: models.Model,
    *,
    csv_map: dict[str, Callable[[list[str]], object]],
    chunk_size: int = 1000,
):
    # Delete all existing
    await model.all().delete()

    with open(path, "r") as f:
        csv_reader = csv.reader(f)
        next(csv_reader)  # Skip header

        sql_models: list[models.Model] = []

        for row in csv_reader:
            kwargs = {arg: getter(row) for arg, getter in csv_map.items()}
            sql_models.append(model(**kwargs))

            if len(sql_models) == chunk_size:
                await model.bulk_create(sql_models)
                sql_models = []

        if len(sql_models) > 0:
            await model.bulk_create(sql_models)


if __name__ == "__main__":
    print("Seeding database...")
    run_async(seed())
    print("Done!")
