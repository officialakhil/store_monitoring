from datetime import datetime, time
from enum import Enum

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, BigInteger, DateTime, Time
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


class StoreStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class DayOfWeekEnum(int, Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class StoreStatus(SQLModel, table=True):
    __tablename__ = "store_status"

    id: int | None = Field(default=None, primary_key=True)
    store_id: int = Field(sa_column=Column(BigInteger(), index=True))
    timestamp_utc: datetime = Field(sa_column=Column(DateTime(True)))
    status: StoreStatusEnum


class StoreBusinessHours(SQLModel, table=True):
    __tablename__ = "store_business_hours"

    id: int | None = Field(default=None, primary_key=True)
    store_id: int = Field(sa_column=Column(BigInteger(), index=True))
    day_of_week: DayOfWeekEnum
    start_time_local: time = Field(sa_column=Column(Time(False)))
    end_time_local: time = Field(sa_column=Column(Time(False)))


class Store(SQLModel, table=True):
    __tablename__ = "stores"

    store_id: int = Field(sa_column=Column(BigInteger(), primary_key=True, index=True))
    timezone_str: str


async_engine = create_async_engine(
    "postgresql+asyncpg://akhiltulluri@localhost:5432/loop"
)


async def create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


class AsyncSessionContextManager:
    def __init__(self):
        self._async_session = sessionmaker(
            async_engine, expire_on_commit=False, class_=AsyncSession
        )

    async def __aenter__(self):
        self.session = self._async_session()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
