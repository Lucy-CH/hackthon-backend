from decimal import Decimal

from app.schema.commute import (
    CommuteRoute,
    CommuteStep,
    TransitFare,
)


def parse_duration(value: str) -> float:
    """Convert a Google duration such as '2214s' to seconds."""
    if not isinstance(value, str) or not value.endswith("s"):
        raise ValueError("Invalid route duration.")

    seconds = Decimal(value[:-1])

    if not seconds.is_finite() or seconds < 0:
        raise ValueError("Route duration must be finite and nonnegative.")

    return float(seconds)


def parse_fare(data: dict | None) -> TransitFare | None:
    if data is None:
        return None

    amount = (
        Decimal(data.get("units", "0"))
        + Decimal(data.get("nanos", 0)) / Decimal("1000000000")
    )

    if not amount.is_finite() or amount < 0:
        raise ValueError("Invalid transit fare.")

    return TransitFare(
        currency=data["currencyCode"],
        amount=amount,
    )


def parse_step(data: dict) -> CommuteStep:
    details = data.get("transitDetails") or {}
    line = details.get("transitLine") or {}
    stops = details.get("stopDetails") or {}

    duration = data.get("staticDuration")

    return CommuteStep(
        travel_mode=data["travelMode"],
        instruction=(
            data.get("navigationInstruction") or {}
        ).get("instructions", ""),
        distance_meters=data.get("distanceMeters"),
        duration_seconds=(
            parse_duration(duration)
            if duration is not None
            else None
        ),
        vehicle_type=(line.get("vehicle") or {}).get("type"),
        line_name=line.get("name"),
        line_short_name=line.get("nameShort"),
        headsign=details.get("headsign"),
        departure_stop=(
            stops.get("departureStop") or {}
        ).get("name"),
        arrival_stop=(
            stops.get("arrivalStop") or {}
        ).get("name"),
        departure_time=stops.get("departureTime"),
        arrival_time=stops.get("arrivalTime"),
        stop_count=details.get("stopCount"),
    )


def parse_commute_route(data: dict) -> CommuteRoute:
    steps = [
        parse_step(step)
        for leg in data.get("legs", [])
        for step in leg.get("steps", [])
    ]

    if not steps:
        raise ValueError("The route contains no navigation steps.")

    transit_steps = [
        step for step in steps
        if step.travel_mode == "TRANSIT"
    ]

    walking_steps = [
        step for step in steps
        if step.travel_mode == "WALK"
    ]

    # Do not report a complete walking distance when a segment is missing.
    walking_distance = (
        sum(
            step.distance_meters
            for step in walking_steps
            if step.distance_meters is not None
        )
        if all(
            step.distance_meters is not None
            for step in walking_steps
        )
        else None
    )

    return CommuteRoute(
        duration_seconds=parse_duration(data["duration"]),
        distance_meters=data["distanceMeters"],
        transfer_count=max(len(transit_steps) - 1, 0),
        walking_distance_meters=walking_distance,
        fare=parse_fare(
            (data.get("travelAdvisory") or {}).get("transitFare")
        ),
        encoded_polyline=(
            data.get("polyline") or {}
        ).get("encodedPolyline"),
        steps=steps,
    )