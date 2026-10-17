from decimal import Decimal

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

from app.schema.commute import CommuteRoute

class RecommendationRequest(BaseModel):
    include_ai: bool = Field(default=True, description="Add DeepSeek picks to the rental list.")
    preferences: str = Field(default="", max_length=1000, description="Optional housing preferences.")
    ai_recommendation_count: int = Field(default=2, ge=1, le=2)
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


class AIRecommendation(BaseModel):
    rental_id: int = Field(gt=0, strict=True)
    reason: str = Field(min_length=1, max_length=1200, pattern=r"\S")
    tradeoff: str = Field(min_length=1, max_length=600, pattern=r"\S")


class AIRecommendationResult(BaseModel):
    status: Literal["disabled", "not_configured", "no_candidates", "success", "unavailable"]
    recommendations: list[AIRecommendation] = Field(default_factory=list)
    considered_count: int = 0
    message: str | None = None


class RecommendationResponse(BaseModel):
    work_address_id: int
    arrival_time: datetime

    candidate_count: int
    no_route_count: int

    items: list[RecommendationItem]
    ai: AIRecommendationResult = Field(
        default_factory=lambda: AIRecommendationResult(status="disabled"),
    )
