# Local auth_settingss
from pathlib import Path

from fastapi_mail import ConnectionConfig
from pydantic import (
    SecretStr,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent.parent

# 2. Define the template folder relative to the project root.
TEMPLATE_DIR = BASE_DIR / "templates"


class AuthConfig(BaseSettings):
    ACCESS_TOKEN_EXPIRY: int = 60  # 60 minutes
    REFRESH_TOKEN_EXPIRY: int = 7  # 7 days
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
    EMAIL_OTP_EXPIRE_MINUTES: int = 5
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


auth_settings = AuthConfig() # type: ignore

conf = ConnectionConfig(
    MAIL_USERNAME=auth_settings.MAIL_USERNAME,
    MAIL_PASSWORD=SecretStr(auth_settings.MAIL_PASSWORD),
    MAIL_FROM=auth_settings.MAIL_FROM,
    MAIL_PORT=auth_settings.MAIL_PORT,
    MAIL_SERVER=auth_settings.MAIL_SERVER,
    MAIL_FROM_NAME=auth_settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=auth_settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=auth_settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=auth_settings.USE_CREDENTIALS,
    VALIDATE_CERTS=auth_settings.VALIDATE_CERTS,
    TEMPLATE_FOLDER=TEMPLATE_DIR,
)
