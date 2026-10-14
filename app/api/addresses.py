from typing import Annotated
from unittest import result
from app.schema.response import ApiResponse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schema.address import AddressSearchResponse
from app.service.address_service import AddressService

router = APIRouter(
    prefix="/api/code-tables",
    tags=["Addresses"],
)

DbSession = Annotated[
    AsyncSession,
    Depends(get_db, scope="function"),
]


@router.get(
    "/address_list",
    response_model=ApiResponse[AddressSearchResponse],
    summary="搜索香港地址",
)
async def search_addresses(
    db: DbSession,
    q: Annotated[
        str,
        Query(
            min_length=1,
            max_length=100,
            description="地址或楼宇名称，多个关键词用空格分隔",
        ),
    ],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=50,
            description="最多返回多少条结果",
        ),
    ] = 10,
) -> ApiResponse[AddressSearchResponse]:
    keyword = " ".join(q.split())

    if not keyword:
        raise HTTPException(
            status_code=422,
            detail="搜索关键词不能为空",
        )

    result = await AddressService(db).search(
    keyword=keyword,
    limit=limit,
)

    return ApiResponse[AddressSearchResponse](data=result)
