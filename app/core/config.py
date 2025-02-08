# File with environment variables and general configuration logic.
# Env variables are combined in nested groups like "Security", "Database" etc.
# So environment variable (case-insensitive) for jwt_secret_key will be "security__jwt_secret_key"
#
# Pydantic priority ordering:
#
# 1. (Most important, will overwrite everything) - environment variables
# 2. `.env` file in root folder of project
# 3. Default values
#
# "sqlalchemy_database_uri" is computed field that will create valid database URL
#
# See https://pydantic-docs.helpmanual.io/usage/settings/
# Note, complex types like lists are read as json-encoded strings.


from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from pydantic import AnyHttpUrl, BaseModel, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import URL, make_url

PROJECT_DIR = Path(__file__).parent.parent.parent


class Security(BaseModel):
    jwt_issuer: str = "my-app"
    jwt_secret_key: SecretStr
    jwt_access_token_expire_secs: int = 24 * 3600  # 1d
    refresh_token_expire_secs: int = 28 * 24 * 3600  # 28d
    password_bcrypt_rounds: int = 12
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    backend_cors_origins: list[AnyHttpUrl] = []


class Database(BaseModel):
    url: Optional[str] = None
    hostname: Optional[str] = None
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    port: Optional[int] = None
    db: Optional[str] = None

    model_config = {
        "arbitrary_types_allowed": True
    }

    @computed_field
    @property
    def sqlalchemy_url(self) -> URL:
        if self.url:
            # Convert the URL string to SQLAlchemy URL object
            return make_url(self.url)
        elif all([self.hostname, self.username, self.password, self.port, self.db]):
            return URL.create(
                drivername="postgresql+asyncpg",
                username=self.username,
                password=self.password.get_secret_value(),
                host=self.hostname,
                port=self.port,
                database=self.db,
            )
        raise ValueError("Either DATABASE__URL or all individual database settings must be provided")


class Settings(BaseSettings):
    security: Security
    database: Database
    port: Optional[int] = None

    @computed_field
    @property
    def sqlalchemy_database_uri(self) -> URL:
        return self.database.sqlalchemy_url

    model_config = SettingsConfigDict(
        env_file=f"{PROJECT_DIR}/.env",
        case_sensitive=False,
        env_nested_delimiter="__",
        arbitrary_types_allowed=True,
        extra='ignore'
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
