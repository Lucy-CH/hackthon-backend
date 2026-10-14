from sqlalchemy import case, func, or_, select

from app.model.address import Address
from app.schema.address import AddressResponse, AddressSearchResponse
from app.service.base import BaseService


class AddressService(BaseService):
    async def search(
        self,
        *,
        keyword: str,
        limit: int = 10,
    ) -> AddressSearchResponse:
        # 去掉首尾空白，并把连续空白统一为一个空格。
        normalized = " ".join(keyword.split())

        if not normalized:
            return AddressSearchResponse(items=[])

        if len(normalized) > 100:
            raise ValueError("搜索关键词不能超过 100 个字符")

        if not 1 <= limit <= 50:
            raise ValueError("limit 必须在 1 到 50 之间")

        # 去掉重复关键词，英文不区分大小写。
        tokens = list(
            dict.fromkeys(
                token.lower()
                for token in normalized.split()
            )
        )

        searchable_fields = (
            Address.building_name_zh,
            Address.building_name_en,
            Address.address_zh,
            Address.address_en,
        )

        # 同一个关键词：匹配任意字段即可。
        # 不同关键词：必须全部匹配同一条地址。
        conditions = [
            or_(
                *[
                    field.icontains(token, autoescape=True)
                    for field in searchable_fields
                ]
            )
            for token in tokens
        ]

        # 排序使用完整输入：
        # 0 = 楼宇名称完全匹配
        # 1 = 楼宇名称前缀匹配
        # 2 = 其他包含匹配
        exact_match = or_(
            func.lower(Address.building_name_zh)
            == normalized.lower(),
            func.lower(Address.building_name_en)
            == normalized.lower(),
        )

        prefix_match = or_(
            Address.building_name_zh.istartswith(
                normalized,
                autoescape=True,
            ),
            Address.building_name_en.istartswith(
                normalized,
                autoescape=True,
            ),
        )

        relevance = case(
            (exact_match, 0),
            (prefix_match, 1),
            else_=2,
        )

        statement = (
            select(Address)
            .where(*conditions)
            .order_by(relevance, Address.id)
            .limit(limit)
        )

        result = await self.db.scalars(statement)

        return AddressSearchResponse(
            items=[
                AddressResponse.model_validate(address)
                for address in result.all()
            ]
        )