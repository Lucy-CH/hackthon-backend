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
    summary="Recommend rentals by commute time",
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