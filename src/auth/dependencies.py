from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.security import decode_token
from src.auth.service import UserService
from src.db.main import get_session
from src.db.models import User
from src.errors import (
    AccessTokenRequired,
    AccountNotVerified,
    InsufficientPermission,
    InvalidToken,
    NotAuthenticated,
    RefreshTokenRequired,
    UserNotActive,
)

user_service = UserService()

# NOTE:
# - auto_error=False: so that we can use our custom 401 error
# instead of default 403
# It returns None if no auth header so we need the check below
# if creds is None:


class TokenBearer(HTTPBearer):
    def __init__(self, auto_error=False):
        super().__init__(auto_error=auto_error)

    async def __call__(
        self, request: Request, session: AsyncSession = Depends(get_session)
    ) -> Any:
        creds = await super().__call__(request)
        if creds is None:
            raise NotAuthenticated()
        token = creds.credentials
        token_data = decode_token(token)

        if not self.token_valid(token):
            raise InvalidToken()

        self.verify_token_data(token_data)

        return token_data

    def token_valid(self, token: str) -> bool:
        token_data = decode_token(token)
        # Return True if the token is valid (decoded successfully), otherwise False
        return token_data is not None

    def verify_token_data(self, token_data):
        raise NotImplementedError("Please Override this method in child classes")


class AccessTokenBearer(TokenBearer):
    """Access tokens are stateless - no Redis check needed"""

    def verify_token_data(self, token_data: dict) -> None:
        if token_data and token_data.get("token_type") != "access":
            raise AccessTokenRequired()


class RefreshTokenBearer(TokenBearer):
    """Refresh tokens must be validated against Redis allowlist"""

    async def __call__(
        self, request: Request, session: AsyncSession = Depends(get_session)
    ):
        # Get token and decode it
        creds = await super(HTTPBearer, self).__call__(request)
        if creds is None:
            raise NotAuthenticated()

        token = creds.credentials

        token_data = decode_token(token)

        if not token_data:
            raise InvalidToken()

        # Validate token type
        if token_data and token_data.get("token_type") != "refresh":
            raise RefreshTokenRequired()

        # Extract data for allowlist check
        jti = token_data.get("jti")
        user_id = token_data.get("user", {}).get("user_id")

        if not jti or not user_id:
            raise InvalidToken()

        # Check if JTI is in user's active sessions (allowlist)
        if not await user_service.is_token_valid(user_id=user_id, jti=jti):
            raise InvalidToken()

        return token_data


async def get_current_user(
    token_details: dict = Depends(
        AccessTokenBearer(),
    ),
    session: AsyncSession = Depends(get_session),
):

    user_id = token_details["user"]["user_id"]

    user = await user_service.get_user(user_id, session)

    if not user:
        raise NotAuthenticated()

    if not user.is_active:
        raise UserNotActive()

    if not user.is_email_verified:
        raise AccountNotVerified()

    return user


class RoleChecker:
    def __init__(self, allowed_roles: list[str]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)):
        if current_user.role in self.allowed_roles:
            return True

        raise InsufficientPermission()
