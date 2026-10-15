from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import Base, IDMixin, TimestampMixin


class RentalListing(IDMixin, TimestampMixin, Base):
    __tablename__ = "rental_listings"

    __table_args__ = (
        CheckConstraint(
            "monthly_rent_hkd > 0",
            name="ck_rental_listings_positive_rent",
        ),
        CheckConstraint(
            "saleable_area_sqft > 0",
            name="ck_rental_listings_positive_area",
        ),
        CheckConstraint(
            "bedrooms >= 0",
            name="ck_rental_listings_nonnegative_bedrooms",
        ),
        CheckConstraint(
            "latitude BETWEEN -90 AND 90",
            name="ck_rental_listings_latitude_range",
        ),
        CheckConstraint(
            "longitude BETWEEN -180 AND 180",
            name="ck_rental_listings_longitude_range",
        ),
    )

    # Original listing ID, used to prevent duplicate imports.
    listing_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
    )

    title: Mapped[str] = mapped_column(Text)
    district: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(Text)

    # Monthly asking rent in HKD.
    monthly_rent_hkd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        index=True,
    )

    saleable_area_sqft: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
    )
    bedrooms: Mapped[int | None] = mapped_column(Integer)

    # Coordinates are required for map display and route planning.
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    listing_url: Mapped[str] = mapped_column(Text)

    # When the original listing data was collected.
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )