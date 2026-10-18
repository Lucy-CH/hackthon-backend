from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.google_routes import GoogleRoutesError
from app.core.database import get_db
from app.schema.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
)
from app.schema.response import ApiResponse
from app.service.recommendation_service import (
    RecommendationService,
    WorkAddressCoordinatesMissingError,
    WorkAddressNotFoundError,
)


router = APIRouter(
    prefix="/api/recommendations",
    tags=["Recommendations"],
)

DbSession = Annotated[
    AsyncSession,
    Depends(get_db, scope="function"),
]


@router.post(
    "",
    response_model=ApiResponse[RecommendationResponse],
    summary="Find rentals by budget and commute with optional DeepSeek picks",
)
async def recommend_rentals(
    request: RecommendationRequest,
    db: DbSession,
) -> ApiResponse[RecommendationResponse]:
    try:
        result = await RecommendationService(db).recommend(request)
    except WorkAddressNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except WorkAddressCoordinatesMissingError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except GoogleRoutesError as exc:
        raise HTTPException(
            status_code=502,
            detail="The routing service is unavailable. Please try again.",
        ) from exc

    return ApiResponse[RecommendationResponse](data=result)


from app.schema.comparison import ComparisonRequest, ComparisonResponse
from app.service.comparison_service import compare_rentals


@router.post("/compare", response_model=ApiResponse[ComparisonResponse])
async def compare_selected_rentals(request: ComparisonRequest, db: DbSession):
    try:
        # Re-fetch server data and routes; never trust client-submitted costs or metrics.
        result = await RecommendationService(db).recommend(
            request.model_copy(update={"include_ai": False}),
            rental_ids=request.rental_ids,
            build_comparison=False,
        )
    except WorkAddressNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GoogleRoutesError as exc:
        raise HTTPException(status_code=502, detail="The routing service is unavailable.") from exc
    by_id = {item.rental_id: item for item in result.items}
    if any(i not in by_id for i in request.rental_ids):
        raise HTTPException(status_code=422, detail="Some selected homes no longer have transit routes. Search again.")
    comparison = await compare_rentals(request, [by_id[i] for i in request.rental_ids])
    return ApiResponse[ComparisonResponse](data=comparison)


from app.model.rental_listing import RentalListing
from app.schema.recommendation import RentalDetail


@router.get("/{rental_id}", response_model=ApiResponse[RentalDetail])
async def rental_details(rental_id: int, db: DbSession):
    rental = await db.get(RentalListing, rental_id)
    if rental is None:
        raise HTTPException(status_code=404, detail="Rental listing not found.")
    return ApiResponse(data=RentalDetail(
        rental_id=rental.id, title=rental.title, address=rental.address,
        district=rental.district, monthly_rent_hkd=rental.monthly_rent_hkd,
        bedrooms=rental.bedrooms, saleable_area_sqft=rental.saleable_area_sqft,
        property_details=rental.property_details or {}, listing_url=rental.listing_url,
        fetched_at=rental.fetched_at,
    ))


@router.post("/{rental_id}/analysis", response_model=ApiResponse[ComparisonResponse])
async def analyze_rental(rental_id: int, request: RecommendationRequest, db: DbSession):
    try:
        result = await RecommendationService(db).recommend(
            request.model_copy(update={"include_ai": False}),
            rental_ids=[rental_id], build_comparison=False,
        )
    except WorkAddressNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GoogleRoutesError as exc:
        raise HTTPException(status_code=502, detail="The routing service is unavailable.") from exc
    if not result.items:
        raise HTTPException(status_code=422, detail="This home has no transit route. Please search again.")
    return ApiResponse(data=await compare_rentals(request, result.items, allow_single=True))
