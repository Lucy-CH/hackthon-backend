from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.addresses import router as address_router
from app.core.config import web_settings
from app.core.database import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

    # 应用停止时释放数据库连接池。
    await get_engine().dispose()


app = FastAPI(
    title=web_settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# 允许配置中的 React 前端访问后端。
app.add_middleware(
    CORSMiddleware,
    allow_origins=web_settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# 注册地址搜索接口。
app.include_router(address_router)