from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from src.auth.schemas import SUCCESS_EXAMPLE


class ProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=50)
    last_name: str | None = Field(default=None, max_length=50)

    avatar_url: str | None = None


class ProfileData(BaseModel):
    # User fields
    id: str
    first_name: str
    last_name: str
    username: str
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)


class ProfileResponse(BaseModel):
    status: str
    message: str
    data: ProfileData


class ProfileListResult(BaseModel):
    id: str
    user_id: str
    username: str
    full_name: str
    avatar_url: HttpUrl | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginationData(BaseModel):
    count: int
    next: str | None = None
    previous: str | None = None
    results: list[ProfileListResult]


class ProfileListResponse(BaseModel):
    status: str
    message: str
    data: PaginationData


class AvatarUploadResponse(BaseModel):
    status: str = SUCCESS_EXAMPLE
    message: str
    avatar_url: HttpUrl
