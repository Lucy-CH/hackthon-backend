from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import db_settings
from app.model import Address  # noqa: F401，导入以注册模型
from app.model.base import Base


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy 模型定义的表结构
target_metadata = Base.metadata

# Alembic 使用同步驱动，连接同一个 PostgreSQL 数据库。
database_url = db_settings.make_url("postgresql+psycopg")


def run_migrations_offline() -> None:
    """生成 SQL，不实际连接数据库。"""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """连接数据库并执行迁移。"""
    engine = create_engine(
        database_url,
        poolclass=pool.NullPool,
    )

    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()