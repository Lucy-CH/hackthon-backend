from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.schema.commute import CommuteRoute
from app.service.emission_factors import (
    EMISSION_FACTOR_VERSION,
    get_emission_factor,
)


@dataclass(frozen=True)
class CommuteEmissions:
    one_way_kg_co2e: Decimal | None
    monthly_kg_co2e: Decimal | None
    factor_version: str = EMISSION_FACTOR_VERSION


def calculate_commute_emissions(
    route: CommuteRoute,
    commuting_days: int = 22,
) -> CommuteEmissions:
    """Estimate emissions, assuming the same route in both directions."""
    if commuting_days <= 0:
        raise ValueError("Commuting days must be greater than zero.")

    unavailable = CommuteEmissions(
        one_way_kg_co2e=None,
        monthly_kg_co2e=None,
    )

    if not route.steps:
        return unavailable

    total = Decimal("0")

    for step in route.steps:
        factor = get_emission_factor(
            travel_mode=step.travel_mode,
            vehicle_type=step.vehicle_type,
        )

        # Do not present partial estimates as complete route emissions.
        if factor is None or step.distance_meters is None:
            return unavailable

        distance_km = Decimal(step.distance_meters) / Decimal("1000")
        total += distance_km * factor

    # Calculate monthly emissions before rounding the single-trip value.
    monthly = total * Decimal("2") * Decimal(commuting_days)

    return CommuteEmissions(
        one_way_kg_co2e=total.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        ),
        monthly_kg_co2e=monthly.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        ),
    )