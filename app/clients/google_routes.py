from datetime import datetime, timezone

import httpx

from app.core.config import google_routes_settings


class GoogleRoutesError(RuntimeError):
    """Raised when the Google Routes API request fails."""


class GoogleRoutesClient:
    URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

    FIELD_MASK = ",".join(
        [
            "routes.duration",
            "routes.distanceMeters",
            "routes.polyline.encodedPolyline",
            "routes.travelAdvisory.transitFare",
            "routes.legs.steps.travelMode",
            "routes.legs.steps.distanceMeters",
            "routes.legs.steps.staticDuration",
            "routes.legs.steps.navigationInstruction",
            "routes.legs.steps.transitDetails",
        ]
    )

    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client
        self.api_key = (
            google_routes_settings.api_key
            .get_secret_value()
            .strip()
        )

        if not self.api_key:
            raise ValueError("GOOGLE_ROUTES_API_KEY is empty.")

    async def compute_transit_routes(
        self,
        *,
        origin_latitude: float,
        origin_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
        arrival_time: datetime,
    ) -> list[dict]:
        if arrival_time.utcoffset() is None:
            raise ValueError("arrival_time must include a timezone.")

        payload = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": origin_latitude,
                        "longitude": origin_longitude,
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": destination_latitude,
                        "longitude": destination_longitude,
                    }
                }
            },
            "travelMode": "TRANSIT",
            "arrivalTime": (
                arrival_time.astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            ),
            "languageCode": "en",
            "units": "METRIC",
        }

        try:
            response = await self.http_client.post(
                self.URL,
                headers={
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": self.FIELD_MASK,
                },
                json=payload,
                timeout=30.0,
            )
        except httpx.TimeoutException as exc:
            raise GoogleRoutesError(
                "The transit route request timed out."
            ) from exc
        except httpx.RequestError as exc:
            raise GoogleRoutesError(
                "Unable to connect to the routing service."
            ) from exc

        if not response.is_success:
            raise GoogleRoutesError(
                "The routing service returned "
                f"HTTP {response.status_code}."
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise GoogleRoutesError(
                "The routing service returned invalid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise GoogleRoutesError(
                "The routing service returned an unexpected response."
            )

        routes = data.get("routes", [])

        if not isinstance(routes, list) or any(
            not isinstance(route, dict) for route in routes
        ):
            raise GoogleRoutesError(
                "The routing service returned invalid route data."
            )

        return routes