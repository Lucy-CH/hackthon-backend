import argparse
import csv
import json
import math
import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from sqlalchemy.dialects.postgresql import insert
from app.core.database import get_engine, get_session_factory
from app.model.rental_listing import RentalListing


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FILE = PROJECT_ROOT / "data/rentals/28hse_rentals.csv"

REQUIRED_COLUMNS = {
    "listing_id",
    "title",
    "district",
    "address",
    "price_hkd",
    "usable_area_sqft",
    "bedrooms",
    "latitude",
    "longitude",
    "url",
    "fetched_at",
}


def positive_decimal(value: str, field: str) -> Decimal:
    number = Decimal(value)

    if not number.is_finite() or number <= 0:
        raise ValueError(f"{field} must be a positive finite number")

    return number


def convert_row(row: dict[str, str]) -> dict | None:
    latitude_text = row["latitude"].strip()
    longitude_text = row["longitude"].strip()

    # Skip records that cannot be placed on the map.
    if not latitude_text or not longitude_text:
        return None

    try:
        latitude = float(latitude_text)
        longitude = float(longitude_text)
    except ValueError:
        return None

    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return None

    for field in (
        "listing_id",
        "title",
        "district",
        "address",
        "url",
        "fetched_at",
    ):
        if not row[field].strip():
            raise ValueError(f"{field} is required")

    area_text = row["usable_area_sqft"].strip()
    bedrooms_text = row["bedrooms"].strip()

    bedrooms = int(bedrooms_text) if bedrooms_text else None

    if bedrooms is not None and bedrooms < 0:
        raise ValueError("bedrooms cannot be negative")

    fetched_at = datetime.fromisoformat(row["fetched_at"].strip())

    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at must include a timezone")

    return {
        "listing_id": row["listing_id"].strip(),
        "title": row["title"].strip(),
        "district": row["district"].strip(),
        "address": row["address"].strip(),
        "monthly_rent_hkd": positive_decimal(
            row["price_hkd"].strip(),
            "price_hkd",
        ),
        "saleable_area_sqft": (
            positive_decimal(area_text, "usable_area_sqft")
            if area_text
            else None
        ),
        "bedrooms": bedrooms,
        "property_details": {
            key: row.get(key, "").strip()[:4000] or None
            for key in ("property_type", "bathrooms", "floor", "kitchen_type",
                        "building_age_years", "estate", "description", "rent_includes",
                        "subletting", "cooking_method", "sharing_type", "sharing_terms")
        },
        "latitude": latitude,
        "longitude": longitude,
        "listing_url": row["url"].strip(),
        "fetched_at": fetched_at,
    }


def read_rentals(path: Path) -> list[dict]:
    rentals = []
    seen = set()
    total = 0
    skipped_coordinates = 0
    skipped_duplicates = 0

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                f"Missing CSV columns: {', '.join(sorted(missing))}"
            )

        for record_number, row in enumerate(reader, start=1):
            total += 1

            try:
                rental = convert_row(row)
            except (ValueError, ArithmeticError, AttributeError) as exc:
                raise ValueError(
                    f"CSV record {record_number} is invalid: {exc}"
                ) from exc

            if rental is None:
                skipped_coordinates += 1
                continue

            listing_id = rental["listing_id"]

            if listing_id in seen:
                skipped_duplicates += 1
                continue

            seen.add(listing_id)
            rentals.append(rental)

    print(f"Total records: {total}")
    print(f"Skipped missing or invalid coordinates: {skipped_coordinates}")
    print(f"Skipped duplicate listing IDs: {skipped_duplicates}")
    print(f"Valid records: {len(rentals)}")

    return rentals

async def import_rentals(rentals: list[dict], update_details: bool = False) -> None:
    if not rentals:
        print("No valid records to import.")
        return

    try:
        async with get_session_factory().begin() as session:
            if update_details:
                from sqlalchemy import update
                updated = 0
                for rental in rentals:
                    # Explicit backfill only: preserve existing rent, coordinates and snapshot dates.
                    result = await session.execute(
                        update(RentalListing).where(RentalListing.listing_id == rental["listing_id"])
                        .values(property_details=rental["property_details"])
                    )
                    updated += result.rowcount
                print(f"Updated property details: {updated}")
                return
            statement = (
                insert(RentalListing)
                .values(rentals)
                .on_conflict_do_nothing(
                    index_elements=[RentalListing.listing_id]
                )
                .returning(RentalListing.id)
            )

            result = await session.execute(statement)
            inserted = len(result.scalars().all())

        # The transaction has committed successfully at this point.
        print(f"Inserted records: {inserted}")
        print(f"Skipped existing records: {len(rentals) - inserted}")
        print("Import complete.")
    finally:
        await get_engine().dispose()

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import rental listings from CSV."
    )
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update-details", action="store_true", help="Update optional property details of existing listings only.")
    args = parser.parse_args()

    rentals = read_rentals(args.file)

    if args.dry_run:
        for rental in rentals[:3]:
            print(
                json.dumps(
                    rental,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )

        print(
            "Preview complete. "
            "No database connection or writes were made."
        )
        return

    asyncio.run(import_rentals(rentals, update_details=args.update_details))

if __name__ == "__main__":
    main()