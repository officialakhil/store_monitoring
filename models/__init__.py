from datetime import datetime
from enum import Enum

from tortoise import fields, models


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


class StoreStatus(models.Model):
    store_id: int = fields.BigIntField(index=True)
    timestamp_utc: datetime = fields.DatetimeField()
    status: StoreStatusEnum = fields.CharEnumField(
        enum_type=StoreStatusEnum, max_length=10
    )

    def __str__(self):
        return self.status

    class Meta:
        table = "store_status"
        ordering = ["-timestamp_utc"]


class StoreBusinessHours(models.Model):
    store_id: int = fields.BigIntField()
    day_of_week: DayOfWeekEnum = fields.IntEnumField(enum_type=DayOfWeekEnum)
    start_time_local: str = fields.CharField(8)
    end_time_local: str = fields.CharField(8)

    def __str__(self):
        return (
            self.day_of_week + " " + self.start_time_local + " " + self.end_time_local
        )

    class Meta:
        table = "store_business_hours"
        ordering = ["day_of_week"]


class Store(models.Model):
    store_id: int = fields.BigIntField(pk=True)
    timezone_str: str = fields.CharField(max_length=255)

    class Meta:
        table = "stores"


__models__ = [StoreStatus, StoreBusinessHours, Store]
