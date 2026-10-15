from decimal import Decimal


# Unit: kg CO2e per passenger-kilometre.
#
# Source: UK Government GHG Conversion Factors 2026.
# Table 23: Average local bus.
# Table 25: Average light rail and tram.
#
# These are UK proxy factors, not measured Hong Kong factors.
# Applying the light rail factor to subway services is an MVP assumption.
# Estimates exclude vehicle/infrastructure manufacture and upstream WTT.

EMISSION_FACTOR_VERSION = "uk_2026_operational_proxy_v1"

EMISSION_FACTOR_SOURCE_URL = (
    "https://assets.publishing.service.gov.uk/media/"
    "6a2940543b15d05a7ce3202e/"
    "2026-GHG-conversion-factors-methodology-report.pdf"
)

URBAN_RAIL_KG_CO2E_PER_PASSENGER_KM = Decimal("0.02444")
BUS_KG_CO2E_PER_PASSENGER_KM = Decimal("0.10151")

TRANSIT_EMISSION_FACTORS: dict[str, Decimal] = {
    "SUBWAY": URBAN_RAIL_KG_CO2E_PER_PASSENGER_KM,
    "METRO_RAIL": URBAN_RAIL_KG_CO2E_PER_PASSENGER_KM,
    "TRAM": URBAN_RAIL_KG_CO2E_PER_PASSENGER_KM,
    "LIGHT_RAIL": URBAN_RAIL_KG_CO2E_PER_PASSENGER_KM,
    "BUS": BUS_KG_CO2E_PER_PASSENGER_KM,
}


def get_emission_factor(
    travel_mode: str,
    vehicle_type: str | None,
) -> Decimal | None:
    """Return kg CO2e per passenger-km, or None if unsupported."""
    if travel_mode == "WALK":
        return Decimal("0")

    if travel_mode != "TRANSIT":
        return None

    return TRANSIT_EMISSION_FACTORS.get(vehicle_type or "")