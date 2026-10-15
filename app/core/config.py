from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL
from pydantic import SecretStr


# config.py 位于 app/core/，向上两级就是后端项目根目录。
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _BaseSettingsWithEnv(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class _CommonSettings(_BaseSettingsWithEnv):
    environment: str = "development"


class _WebSettings(_BaseSettingsWithEnv):
    app_name: str = "Hackthon Backend Api"
    cors_origins: str = ""

    model_config = SettingsConfigDict(env_prefix="WEB_")

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


class _DBSettings(_BaseSettingsWithEnv):
    host: str
    port: int
    name: str
    user: str
    password: str

    model_config = SettingsConfigDict(env_prefix="DB_")

    def make_url(self, driver: str) -> URL:
        return URL.create(
            drivername=driver,
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.name,
        )

class _GoogleRoutesSettings(_BaseSettingsWithEnv):
    api_key: SecretStr

    model_config = SettingsConfigDict(
        env_prefix="GOOGLE_ROUTES_",
    )


common_settings = _CommonSettings()
web_settings = _WebSettings()
db_settings = _DBSettings()
google_routes_settings = _GoogleRoutesSettings()