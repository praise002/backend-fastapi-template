import enum
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import EmailStr
from sqlalchemy import Column, DateTime, Integer, String, func
from sqlmodel import Field, Relationship, SQLModel

from src.auth.config import auth_settings


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    first_name: str = Field(max_length=50, min_length=1)
    last_name: str = Field(max_length=50, min_length=1)
    username: str = Field(
        sa_column=Column(String(50), nullable=False, unique=True), min_length=1
    )
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    google_id: str | None = Field(
        sa_column=Column(String(50), unique=True), default=None
    )
    auth_provider: str | None = Field(max_length=50, default=None, nullable=True)
    hashed_password: str | None = Field(default=None, exclude=True, nullable=True)
    is_active: bool = True
    is_superuser: bool = False
    is_email_verified: bool = False
    role: UserRole = Field(default=UserRole.user)

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )
    # created_at: datetime | None = Field(
    #     default_factory=get_datetime_utc,
    #     sa_type=DateTime(timezone=True)
    # )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),  # Database-side default
            onupdate=func.now(),
            nullable=False,
        ),
    )

    otps: list["Otp"] | None = Relationship(
        back_populates="user", passive_deletes="all"
    )
    profile: "Profile" = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "uselist": False},
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return self.full_name


class Otp(SQLModel, table=True):
    id: int = Field(sa_column=Column(Integer, primary_key=True, autoincrement=True))
    otp: int
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )

    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="CASCADE"
    )
    user: User | None = Relationship(back_populates="otps")

    @property
    def is_valid(self) -> bool:
        """
        Check if the OTP is still valid based on expiration settings.
        """
        if self.created_at is None:
            return False

        expiration_time = self.created_at + timedelta(
            minutes=getattr(auth_settings, "EMAIL_OTP_EXPIRE_MINUTES", 15)
        )
        return get_datetime_utc() < expiration_time

    def __repr__(self):
        return str(self.otp)

class Profile(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", unique=True, ondelete="CASCADE"
    )
    user: User | None = Relationship(back_populates="profile")
    # "https://res.cloudinary.com/dq0ow9lxw/image/upload/v1732236186/default-image_foxagq.jpg", - more useful in Django MVT
    avatar_url: str | None = Field(
        default=None,
        max_length=200,
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),  # Database-side default
            onupdate=func.now(),
            nullable=False,
        ),
    )

    def __repr__(self):
        return self.user.full_name  # type: ignore


