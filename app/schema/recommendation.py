from decimal import Decimal

from pydantic import BaseModel, Field
from datetime import datetime

from app.schema.commute import CommuteRoute

class RecommendationRequest(BaseModel):
    work_address_id: int = Field(
        gt=0,
        description="ID of the selected work destination.",
    )

    max_monthly_rent_hkd: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
        description="Maximum monthly rent in HKD, excluding transport.",
    )

class RecommendationItem(BaseModel):
    rental_id: int
    title: str
    address: str
    district: str

    monthly_rent_hkd: Decimal
    estimated_monthly_transport_hkd: Decimal | None = None
    estimated_monthly_total_hkd: Decimal | None = None

    estimated_one_way_co2e_kg: Decimal | None = Field(default=None, ge=0)
    estimated_monthly_co2e_kg: Decimal | None = Field(default=None, ge=0)
    emission_factor_version: str

    latitude: float
    longitude: float

    listing_url: str
    fetched_at: datetime

    commute: CommuteRoute


class RecommendationResponse(BaseModel):
    work_address_id: int
    arrival_time: datetime

    candidate_count: int
    no_route_count: int

    items: list[RecommendationItem]