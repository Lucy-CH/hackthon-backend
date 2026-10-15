from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TransitFare(BaseModel):
    currency: str
    amount: Decimal = Field(ge=0)


class CommuteStep(BaseModel):
    travel_mode: str
    instruction: str = ""

    distance_meters: int | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)

    # Present for public transport steps.
    vehicle_type: str | None = None
    line_name: str | None = None
    line_short_name: str | None = None
    headsign: str | None = None

    departure_stop: str | None = None
    arrival_stop: str | None = None

    departure_time: datetime | None = None
    arrival_time: datetime | None = None

    stop_count: int | None = Field(default=None, ge=0)


class CommuteRoute(BaseModel):
    duration_seconds: float = Field(ge=0)
    distance_meters: int = Field(ge=0)

    transfer_count: int = Field(ge=0)
    walking_distance_meters: int | None = Field(default=None, ge=0)

    fare: TransitFare | None = None
    encoded_polyline: str | None = None

    steps: list[CommuteStep]