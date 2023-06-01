import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

from arq import ArqRedis
from arq.connections import RedisSettings
from db import (
    AsyncSessionContextManager,
    Store,
    StoreBusinessHours,
    StoreStatus,
    StoreStatusEnum,
)
from redis.commands.json.path import Path as JsonPath
from sqlmodel import desc, distinct, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

# Note: Typing for AsyncSession.exec() is kinda broken
# See: https://github.com/tiangolo/sqlmodel/pull/58


@dataclass
class UptimeDowntime:
    store_id: int
    uptime_last_hour: float = 0
    downtime_last_hour: float = 0
    uptime_last_day: float = 0
    downtime_last_day: float = 0
    uptime_last_week: float = 0
    downtime_last_week: float = 0


@dataclass
class StoreDetails:
    store_id: int
    store_timezone: str
    store_business_hours: dict[int, list[StoreBusinessHours]]


def within_business_hours(store: StoreDetails, timestamp: datetime) -> bool:
    """Check if timestamp falls within business hours for the store

    Args:
        store (StoreDetails): details of the store
        timestamp (datetime): timestamp to check

    Returns:
        bool: True if timestamp falls within business hours, False otherwise
    """
    local_ts = timestamp.astimezone(ZoneInfo(store.store_timezone))
    business_hours = store.store_business_hours.get(local_ts.weekday(), [])

    return any(
        [
            business_hour.start_time_local
            <= local_ts.time()
            <= business_hour.end_time_local
            for business_hour in business_hours
        ]
    )


def calculate_business_hours(
    start_time: datetime, end_time: datetime, store: StoreDetails
):
    """Calculate the number of seconds between start_time and end_time
    such that only business hours are considered

    Args:
        start_time (datetime): an offset-aware datetime object
        end_time (datetime): an offset-aware datetime object
        store (StoreDetails): details of the store

    Returns:
        float: number of seconds between start_time and end_time
    """
    ts = start_time
    timez = ZoneInfo(store.store_timezone)
    diff = 0

    while ts <= end_time:
        local_ts = ts.astimezone(timez)
        local_end_time = end_time.astimezone(timez)

        business_hours = store.store_business_hours.get(local_ts.weekday(), [])
        nearest_business_end_hours = [
            business_hour.end_time_local
            for business_hour in business_hours
            if business_hour.start_time_local
            <= local_ts.time()
            <= business_hour.end_time_local
        ]  # same day

        if (
            nearest_business_end_hours
        ):  # This condition fails when time frame start is outside business hours
            nearest_business_end_hour = min(nearest_business_end_hours)

            nearest_business_end_time = datetime.combine(
                local_ts.date(), nearest_business_end_hour, timez
            )

            if local_end_time <= nearest_business_end_time:
                diff += (local_end_time - local_ts).total_seconds()
                break

            diff += (nearest_business_end_time - local_ts).total_seconds()
        # else: we gotta find next business hour start

        # Try finding nearest business start hour on same day
        # or next day if not found
        next_business_start_hours: list[datetime.time] = [
            business_hour.start_time_local
            for business_hour in business_hours
            if business_hour.start_time_local > local_ts.time()
        ]
        nearest_business_start_hour = (
            min(next_business_start_hours)  # same day
            if next_business_start_hours
            else min(
                [
                    business_hour.start_time_local
                    for business_hour in store.store_business_hours.get(
                        (local_ts.weekday() + 1) % 7, []
                    )
                ]
            )  # next day
        )

        new_date = local_ts.date()

        if not next_business_start_hours:
            new_date = local_ts.date() + timedelta(days=1)

        ts = datetime.combine(new_date, nearest_business_start_hour, timez).astimezone(
            ZoneInfo("UTC")
        )

        if ts > end_time:
            # If new start time is greater than end time, we are done
            break

    return diff


def calculate_uptime_downtime_tf(
    store: StoreDetails,
    *,
    observation_timestamp: datetime,
    current_timestamp: datetime,
    status: StoreStatusEnum,
    prev_observation_timestamp: datetime | None,
):
    """Calculate uptime/downtime for a time frame

    Args:
        store (StoreDetails): details of the store
        observation_timestamp (datetime): Current observation timestamp
        current_timestamp (datetime): This is now() or max timestamp
        status (StoreStatusEnum): Status based on which uptime/downtime is calculated
        prev_observation_timestamp (datetime | None): Previous observation timestamp

    Returns:
        tuple[float,float]: A tuple representing seconds of uptime and downtime
        to be added to the total
    """
    time_diff = (
        calculate_business_hours(
            observation_timestamp, prev_observation_timestamp, store
        )  # If there is a previous observation
        if prev_observation_timestamp
        else calculate_business_hours(
            observation_timestamp, current_timestamp, store
        )  # This is the first observation
    )

    if status == StoreStatusEnum.ACTIVE:
        return time_diff, 0
    else:
        return 0, time_diff


async def get_timezone(session: AsyncSession, store_id: int):
    """Get timezone of a store from database. If not found, America/Chicago is returned

    Args:
        session (AsyncSession): The database session
        store_id (int): ID of the store

    Returns:
        str: Timezone string
    """
    store_timezone = select(Store.timezone_str).where(Store.store_id == store_id)
    timezone_row = await session.exec(store_timezone)
    timezone = timezone_row.one_or_none()
    timezone = cast(str, timezone) if timezone else None

    if timezone is None:
        timezone = "America/Chicago"

    return timezone


async def get_business_hours_map(session: AsyncSession, store_id: int):
    """Get business hours of a store from database and arrange them by day of week

    Args:
        session (AsyncSession): The database session
        store_id (int): ID of the store

    Returns:
        dict[int, list[StoreBusinessHours]]: A mapping between
        day of week and business hours. If no business hours are found for a day,
        it is filled with 24/7
    """
    store_business_hours = (
        select(StoreBusinessHours)
        .where(StoreBusinessHours.store_id == store_id)
        .order_by(StoreBusinessHours.day_of_week, StoreBusinessHours.start_time_local)
    )
    business_hours = await session.exec(store_business_hours)
    business_hours_day_map: dict[int, list[StoreBusinessHours]] = {}

    for business_hour in business_hours:
        business_hour = cast(StoreBusinessHours, business_hour)

        if business_hour.day_of_week not in business_hours_day_map:
            business_hours_day_map[business_hour.day_of_week] = []

        business_hours_day_map[business_hour.day_of_week].append(business_hour)
    # Fill missing days with 24/7
    for day in range(7):
        if day not in business_hours_day_map:
            business_hours_day_map[day] = [
                StoreBusinessHours(
                    day_of_week=day,
                    store_id=store_id,
                    start_time_local=datetime.min.time(),
                    end_time_local=datetime.max.time(),
                )
            ]

    return business_hours_day_map


async def calc_uptime_downtime_store(
    session: AsyncSession, store_id: int, current_timestamp: datetime
):
    """Calcuate uptime/downtime for a store

    Args:
        session (AsyncSession): The database session
        store_id (int): ID of the store
        current_timestamp (datetime): This is now() or max timestamp

    Returns:
        UptimeDowntime: an instance of UptimeDowntime which has
        different uptime/downtime values for different time frames
    """
    # Get store timezone
    timezone = await get_timezone(session, store_id)

    # Get store's business hours and arrange them by day of week
    business_hours_day_map = await get_business_hours_map(session, store_id)

    store = StoreDetails(
        store_id=store_id,
        store_timezone=timezone,
        store_business_hours=business_hours_day_map,
    )

    # Uptime/Downtime is calculated between the current timestamp
    # and the start of the time frame
    last_hour_start = current_timestamp - timedelta(hours=1)
    last_day_start = current_timestamp - timedelta(days=1)
    last_week_start = current_timestamp - timedelta(weeks=1)

    # Initialize uptime/downtime counters
    uptime_downtime_result = UptimeDowntime(store_id=store_id)

    # Get observations for the store
    observations = (
        select(StoreStatus)
        .where(
            StoreStatus.store_id == store_id,
            StoreStatus.timestamp_utc <= current_timestamp,
        )
        .order_by(desc(StoreStatus.timestamp_utc))  # Latest first
    )

    observation: StoreStatus
    obs_stream = await session.stream(observations)

    # These help knowing what is the last seen observation
    first_observation_last_hour: StoreStatus | None = None
    first_observation_last_day: StoreStatus | None = None
    first_observation_last_week: StoreStatus | None = None

    # These help knowing what is the status before the start of the time frame
    # so that we can fill in the gaps
    first_observation_before_last_hour: StoreStatus | None = None
    first_observation_before_last_day: StoreStatus | None = None
    first_observation_before_last_week: StoreStatus | None = None

    async for (observation,) in obs_stream:
        # Check if observation falls in business hours
        # for the day of week it was observed
        if not within_business_hours(store, observation.timestamp_utc):
            # Don't consider observations outside business hours
            continue

        # Check if observation is within the last hour
        if observation.timestamp_utc >= last_hour_start:
            uptime, downtime = calculate_uptime_downtime_tf(
                store,
                observation_timestamp=observation.timestamp_utc,
                current_timestamp=current_timestamp,
                status=observation.status,
                prev_observation_timestamp=first_observation_last_hour.timestamp_utc
                if first_observation_last_hour
                else None,
            )
            uptime_downtime_result.uptime_last_hour += uptime / 60
            uptime_downtime_result.downtime_last_hour += downtime / 60
            first_observation_last_hour = observation
        else:  # Before last hour
            if not first_observation_before_last_hour:
                first_observation_before_last_hour = observation

        # Check if observation is within the last day
        if observation.timestamp_utc >= last_day_start:
            uptime, downtime = calculate_uptime_downtime_tf(
                store,
                observation_timestamp=observation.timestamp_utc,
                current_timestamp=current_timestamp,
                status=observation.status,
                prev_observation_timestamp=first_observation_last_day.timestamp_utc
                if first_observation_last_day
                else None,
            )
            uptime_downtime_result.uptime_last_day += uptime / (60 * 60)
            uptime_downtime_result.downtime_last_day += downtime / (60 * 60)
            first_observation_last_day = observation
        else:  # Before last day
            if not first_observation_before_last_day:
                first_observation_before_last_day = observation

        # Check if observation is within the last week
        if observation.timestamp_utc >= last_week_start:
            uptime, downtime = calculate_uptime_downtime_tf(
                store,
                observation_timestamp=observation.timestamp_utc,
                current_timestamp=current_timestamp,
                status=observation.status,
                prev_observation_timestamp=first_observation_last_week.timestamp_utc
                if first_observation_last_week
                else None,
            )
            uptime_downtime_result.uptime_last_week += uptime / (60 * 60)
            uptime_downtime_result.downtime_last_week += downtime / (60 * 60)
            first_observation_last_week = observation
        else:  # Before last week
            if not first_observation_before_last_week:
                first_observation_before_last_week = observation
                break

    # Fill in the gaps
    if first_observation_before_last_hour:
        # If no observation in last hour, consider current timestamp
        prev_ts = (
            (first_observation_last_hour.timestamp_utc)
            if first_observation_last_hour
            else current_timestamp
        )
        uptime, downtime = calculate_uptime_downtime_tf(
            store,
            observation_timestamp=last_hour_start,
            current_timestamp=current_timestamp,
            status=first_observation_before_last_hour.status,
            prev_observation_timestamp=prev_ts,
        )
        uptime_downtime_result.uptime_last_hour += uptime / 60
        uptime_downtime_result.downtime_last_hour += downtime / 60

    if first_observation_before_last_day:
        prev_ts = (
            (first_observation_last_day.timestamp_utc)
            if first_observation_last_day
            else current_timestamp
        )
        uptime, downtime = calculate_uptime_downtime_tf(
            store,
            observation_timestamp=last_day_start,
            current_timestamp=current_timestamp,
            status=first_observation_before_last_day.status,
            prev_observation_timestamp=prev_ts,
        )
        uptime_downtime_result.uptime_last_day += uptime / (60 * 60)
        uptime_downtime_result.downtime_last_day += downtime / (60 * 60)

    if first_observation_before_last_week:
        prev_ts = (
            (first_observation_last_week.timestamp_utc)
            if first_observation_last_week
            else current_timestamp
        )
        uptime, downtime = calculate_uptime_downtime_tf(
            store,
            observation_timestamp=last_week_start,
            current_timestamp=current_timestamp,
            status=first_observation_before_last_week.status,
            prev_observation_timestamp=prev_ts,
        )
        uptime_downtime_result.uptime_last_week += uptime / (60 * 60)
        uptime_downtime_result.downtime_last_week += downtime / (60 * 60)

    return uptime_downtime_result


async def calculate_uptime_downtime_async(
    ctx: dict[Any, Any], current_timestamp: datetime
) -> int:
    """Calculate uptime/downtime for all stores.
    NOTE: This function should be called using arqredis
    and not directly in an api handler
    as it is a long running task.

    Args:
        ctx (dict[Any, Any]): The arq job context
        current_timestamp (datetime): This is now() or max timestamp

    Returns:
        int: Number of stores processed
    """
    redis = ctx["redis"]
    redis = cast(ArqRedis, redis)

    skip = await redis.json().get(
        f"job:{ctx['job_id']}:progress", JsonPath(".stores_processed")
    )
    skip = cast(int | None, skip)

    if not skip:
        skip = 0
    else:
        print(f"Skipping {skip} stores as they were already processed")
    count = skip

    OUTPUT_FILE_PATH = Path(__file__).parent / f"reports/{ctx['job_id']}.csv"
    async with AsyncSessionContextManager() as session:
        # This is the only table that has all store ids
        get_store_ids = (
            select(StoreStatus.store_id)
            .distinct()
            .order_by(
                StoreStatus.store_id
            )  # This is to ensure that the order is consistent
            .offset(skip)
        )
        count_store_ids = select(func.count(distinct(StoreStatus.store_id)))

        total_stores: int = (await session.exec(count_store_ids)).one()

        stream = await session.stream(get_store_ids)
        store_id: int

        with OUTPUT_FILE_PATH.open("a+") as f:
            if skip == 0:
                f.write(
                    "store_id,uptime_last_hour (minutes),uptime_last_day (hours),uptime_last_week (hours),downtime_last_hour (minutes),downtime_last_day (hours),downtime_last_week (hours)\n"  # noqa: E501
                )
            async for (store_id,) in stream:
                uptime_downtime_result = await calc_uptime_downtime_store(
                    session, store_id, current_timestamp
                )
                f.write(
                    f"{store_id},{uptime_downtime_result.uptime_last_hour:.2f},{uptime_downtime_result.uptime_last_day:.2f},{uptime_downtime_result.uptime_last_week:.2f},{uptime_downtime_result.downtime_last_hour:.2f},{uptime_downtime_result.downtime_last_day:.2f},{uptime_downtime_result.downtime_last_week:.2f}\n"
                )
                await redis.json().set(
                    f"job:{ctx['job_id']}:progress",
                    "$",
                    {"stores_processed": count + 1, "total_stores": total_stores},
                )
                count += 1

    return count


class WorkerSettings:
    redis_settings = RedisSettings(host=os.getenv("REDIS_HOST", "localhost"))
    functions = [calculate_uptime_downtime_async]
    # Having more than 1 job at a time is not working properly TODO: investigate
    max_jobs = 1  # This is to ensure that only one job is processed at a time
