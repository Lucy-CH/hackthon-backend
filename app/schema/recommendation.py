from decimal import Decimal

from pydantic import BaseModel, Field, model_validator
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

class RentalDetail(BaseModel):
    rental_id: int
    title: str
    address: str
    district: str
    monthly_rent_hkd: Decimal
    bedrooms: int | None = None
    saleable_area_sqft: Decimal | None = None
    property_details: dict[str, str | None] = Field(default_factory=dict)
    listing_url: str
    fetched_at: datetime


class RecommendationItem(BaseModel):
    rental_id: int
    title: str
    address: str
    district: str

    monthly_rent_hkd: Decimal
    bedrooms: int | None = None
    saleable_area_sqft: Decimal | None = None
    property_details: dict[str, str | None] = Field(default_factory=dict)
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


class ComparisonRequest(RecommendationRequest):
    rental_ids: list[int] = Field(min_length=2, max_length=3)

    @model_validator(mode="after")
    def unique_ids(self):
        if len(set(self.rental_ids)) != len(self.rental_ids) or any(i <= 0 for i in self.rental_ids):
            raise ValueError("Choose 2–3 different positive rental IDs.")
        return self


class ComparisonAnalysis(BaseModel):
    rental_id: int = Field(gt=0, strict=True)
    strengths: str = Field(min_length=1, max_length=800, pattern=r"\S")
    tradeoffs: str = Field(min_length=1, max_length=800, pattern=r"\S")
    suitable_for: str = Field(min_length=1, max_length=500, pattern=r"\S")


class ComparisonNarrative(BaseModel):
    recommended_rental_id: int = Field(gt=0, strict=True)
    conclusion: str = Field(min_length=1, max_length=1500, pattern=r"\S")
    analyses: list[ComparisonAnalysis] = Field(min_length=1, max_length=3)


class ComparisonDifference(BaseModel):
    rental_id: int
    baseline_rental_id: int
    rent_hkd: Decimal
    commute_seconds: float
    transfers: int
    walking_meters: int | None
    monthly_transport_hkd: Decimal | None
    monthly_total_hkd: Decimal | None
    monthly_co2e_kg: Decimal | None


class ComparisonResponse(BaseModel):
    # Listings and differences always come from backend data, never AI output.
    items: list[RecommendationItem]
    differences: list[ComparisonDifference]
    status: Literal["disabled", "insufficient_candidates", "not_configured", "success", "unavailable"]
    narrative: ComparisonNarrative | None = None
    message: str | None = None


class RecommendationResponse(BaseModel):
    work_address_id: int
    arrival_time: datetime

    candidate_count: int
    no_route_count: int

    items: list[RecommendationItem]
    comparison: ComparisonResponse | None = None
    ai: AIRecommendationResult = Field(
        default_factory=lambda: AIRecommendationResult(status="disabled"),
    )
