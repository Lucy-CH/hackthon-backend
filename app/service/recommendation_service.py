from decimal import Decimal

from sqlalchemy import select

from app.model.address import Address
from app.model.rental_listing import RentalListing
from app.service.base import BaseService

import httpx

from app.clients.google_routes import GoogleRoutesClient
from app.schema.recommendation import (
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
)
from app.service.commute_parser import parse_commute_route
from app.service.commute_time import next_weekday_arrival

COMMUTING_DAYS_PER_MONTH = 22
TRIPS_PER_DAY = 2

class WorkAddressNotFoundError(ValueError):
    pass


class WorkAddressCoordinatesMissingError(ValueError):
    pass


class RecommendationService(BaseService):
    async def get_work_address(
        self,
        work_address_id: int,
    ) -> Address:
        address = await self.db.get(Address, work_address_id)

        if address is None:
            raise WorkAddressNotFoundError(
                "The selected work destination does not exist."
            )

        if address.latitude is None or address.longitude is None:
            raise WorkAddressCoordinatesMissingError(
                "The selected work destination has no coordinates."
            )

        return address

    async def find_rental_candidates(
        self,
        max_monthly_rent_hkd: Decimal,
    ) -> list[RentalListing]:
        statement = (
            select(RentalListing)
            .where(
                RentalListing.monthly_rent_hkd
                <= max_monthly_rent_hkd,
                RentalListing.latitude.is_not(None),
                RentalListing.longitude.is_not(None),
            )
            .order_by(
                RentalListing.monthly_rent_hkd,
                RentalListing.id,
            )
        )

        result = await self.db.scalars(statement)

        return list(result.all())
    
    async def recommend(
        self,
        request: RecommendationRequest,
    ) -> RecommendationResponse:
        work_address = await self.get_work_address(
            request.work_address_id,
        )

        rentals = await self.find_rental_candidates(
            request.max_monthly_rent_hkd,
        )

        # Use the same arrival time for every candidate.
        arrival_time = next_weekday_arrival()

        response = RecommendationResponse(
            work_address_id=work_address.id,
            arrival_time=arrival_time,
            candidate_count=len(rentals),
            no_route_count=0,
            items=[],
        )

        if not rentals:
            return response

        # Already checked by get_work_address().
        latitude = work_address.latitude
        longitude = work_address.longitude

        if latitude is None or longitude is None:
            raise WorkAddressCoordinatesMissingError(
                "The selected work destination has no coordinates."
            )

        async with httpx.AsyncClient() as http_client:
            routes_client = GoogleRoutesClient(http_client)

            for rental in rentals:
                routes = await routes_client.compute_transit_routes(
                    origin_latitude=rental.latitude,
                    origin_longitude=rental.longitude,
                    destination_latitude=latitude,
                    destination_longitude=longitude,
                    arrival_time=arrival_time,
                )

                if not routes:
                    response.no_route_count += 1
                    continue

                commutes = [
                    parse_commute_route(route)
                    for route in routes
                ]

                # Choose among the routes actually returned by Google.
                commute = min(
                    commutes,
                    key=lambda item: (
                        item.duration_seconds,
                        item.transfer_count,
                    ),
                )

                monthly_transport = None
                monthly_total = None

                if commute.fare is not None and commute.fare.currency == "HKD":
                    monthly_transport = (
                        commute.fare.amount
                        * COMMUTING_DAYS_PER_MONTH
                        * TRIPS_PER_DAY
                    ).quantize(Decimal("0.01"))

                    monthly_total = (
                        rental.monthly_rent_hkd + monthly_transport
                    ).quantize(Decimal("0.01"))

                response.items.append(
                    RecommendationItem(
                        rental_id=rental.id,
                        title=rental.title,
                        address=rental.address,
                        district=rental.district,
                        monthly_rent_hkd=rental.monthly_rent_hkd,
                        estimated_monthly_transport_hkd=monthly_transport,
                        estimated_monthly_total_hkd=monthly_total,
                        latitude=rental.latitude,
                        longitude=rental.longitude,
                        listing_url=rental.listing_url,
                        fetched_at=rental.fetched_at,
                        commute=commute,
                    )
                )

        # Shorter commute first; lower rent breaks ties.
        response.items.sort(
            key=lambda item: (
                item.commute.duration_seconds,
                item.monthly_rent_hkd,
                item.rental_id,
            )
        )

        return response