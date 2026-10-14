from pydantic import BaseModel, ConfigDict


class AddressResponse(BaseModel):
    """一个地址搜索结果。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    geo_address: str | None

    building_name_zh: str | None
    building_name_en: str | None

    address_zh: str
    address_en: str

    district_zh: str | None
    district_en: str | None

    latitude: float | None
    longitude: float | None


class AddressSearchResponse(BaseModel):
    """地址搜索接口的返回数据。"""

    items: list[AddressResponse]