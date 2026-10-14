from sqlalchemy import CheckConstraint, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import Base, IDMixin, TimestampMixin


class Address(IDMixin, TimestampMixin, Base):
    __tablename__ = "addresses"

    __table_args__ = (
        # 经纬度必须同时存在，或者同时为空。
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_addresses_coordinates_pair",
        ),
        CheckConstraint(
            "latitude BETWEEN -90 AND 90",
            name="ck_addresses_latitude_range",
        ),
        CheckConstraint(
            "longitude BETWEEN -180 AND 180",
            name="ck_addresses_longitude_range",
        ),
    )

    # 同一位置可能对应多个文字地址，因此不设置唯一约束。
    geo_address: Mapped[str | None] = mapped_column(
        String(19),
        index=True,
    )

    # 中英文楼宇名称
    building_name_zh: Mapped[str | None] = mapped_column(String(255))
    building_name_en: Mapped[str | None] = mapped_column(String(255))

    # 中英文完整地址
    address_zh: Mapped[str] = mapped_column(Text)
    address_en: Mapped[str] = mapped_column(Text)

    # 中英文地区名称
    district_zh: Mapped[str | None] = mapped_column(String(100))
    district_en: Mapped[str | None] = mapped_column(String(100))

    # WGS84 经纬度
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    @property
    def has_coordinates(self) -> bool:
        return (
            self.latitude is not None
            and self.longitude is not None
        )