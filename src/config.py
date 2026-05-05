import secrets
import warnings
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal

import cloudinary
from fastapi_mail import ConnectionConfig
from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    SecretStr,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


def empty_to_none(v: Any) -> Any:
    if v == "" or v is None:
        return None
    return v


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    ACCESS_TOKEN_EXPIRY: int = 60  # 60 minutes
    REFRESH_TOKEN_EXPIRY: int = 7  # 7 days
    DATABASE_URL: str | None = None
    REDIS_URL: str = "redis://localhost:6379/0"
    JWT_SECRET: str
    JWT_ALGORITHM: str 
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_FROM_NAME: str
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True  # Ensures email authentication is enabled.
    VALIDATE_CERTS: bool = True  # Ensures email server certificates are validated
    DOMAIN: str
    EMAIL_OTP_EXPIRE_MINUTES: int = 5
    SECRET_KEY: str = secrets.token_urlsafe(32)
    FRONTEND_HOST: str = "http://localhost:5173"
    FRONTEND_CALLBACK_URL: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str

    # BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    BACKEND_CORS_ORIGINS: Annotated[list[AnyUrl] | str, BeforeValidator(parse_cors)] = (
        []
    )

    @computed_field
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str
    SENTRY_DSN: Annotated[HttpUrl | None, BeforeValidator(empty_to_none)] = None
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_HOST: str | None = None
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str | None = None

    ENVIRONMENT: Literal["local", "production"] = "local"

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )
        return self

    @model_validator(mode="after")
    def _assemble_db_url(self) -> Self:
        if not hasattr(self, "DATABASE_URL") or self.DATABASE_URL is None:
            if all(
                [
                    self.POSTGRES_USER,
                    self.POSTGRES_PASSWORD,
                    self.POSTGRES_HOST,
                    self.POSTGRES_DB,
                ]
            ):
                self.DATABASE_URL = f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            else:
                raise ValueError(
                    "DATABASE_URL or all POSTGRES_* variables must be provided"
                )
        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


Config = Settings()  # type: ignore

broker_url = Config.REDIS_URL
result_backend = Config.REDIS_URL
broker_connection_retry_on_startup = True

conf = ConnectionConfig(
    MAIL_USERNAME=Config.MAIL_USERNAME,
    MAIL_PASSWORD=SecretStr(Config.MAIL_PASSWORD),
    MAIL_FROM=Config.MAIL_FROM,
    MAIL_PORT=Config.MAIL_PORT,
    MAIL_SERVER=Config.MAIL_SERVER,
    MAIL_FROM_NAME=Config.MAIL_FROM_NAME,
    MAIL_STARTTLS=Config.MAIL_STARTTLS,
    MAIL_SSL_TLS=Config.MAIL_SSL_TLS,
    USE_CREDENTIALS=Config.USE_CREDENTIALS,
    VALIDATE_CERTS=Config.VALIDATE_CERTS,
    TEMPLATE_FOLDER=Path("templates"),
)


cloudinary.config(
    cloud_name=Config.CLOUDINARY_CLOUD_NAME,
    api_key=Config.CLOUDINARY_API_KEY,
    api_secret=Config.CLOUDINARY_API_SECRET,
    secure=True,
)
