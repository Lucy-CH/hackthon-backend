from typing import Generic, Literal, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard response envelope for successful requests."""

    code: Literal["0"] = "0"
    data: T
    message: str = "success"