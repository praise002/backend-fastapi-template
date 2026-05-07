"""
Dependencies (Cross-Cutting)
=============================
Reusable FastAPI dependency functions injected into controllers.
They act as guards: extracting, validating, and providing data to route handlers.

Dependency direction: inward only.
  - Imports from: services, infrastructure/security, domain/schemas
  - Must NOT import from: routers (no circular deps)

FastAPI caches dependency results per-request by default, so these are
safe to use in multiple route parameters without duplicate DB hits.
"""
from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.errors import (
    AccessTokenRequired,
    AccountNotVerified,
    InvalidToken,
    NotAuthenticated,
    RefreshTokenRequired,
    UserNotActive,
)
from src.auth.redis import RedisService
from src.auth.security import decode_token
from src.auth.service import UserService
from src.db.database import get_session
from src.db.models import User
from src.exceptions import InsufficientPermission


def get_redis(request: Request) -> RedisService:
    return request.app.state.redis

# NOTE:
# - auto_error=False: so that we can use our custom 401 error
# instead of default 403
# It returns None if no auth header so we need the check below
# if creds is None:

def get_user_service() -> UserService:
    return UserService()

class TokenBearer(HTTPBearer):
    """
    Base class for JWT bearer extraction.

    auto_error=False lets us raise our own typed errors instead of
    FastAPI's default 403 response.
    """

    def __init__(self, auto_error: bool = False):
        super().__init__(auto_error=auto_error)

    async def __call__(
        self, request: Request, session: AsyncSession = Depends(get_session)
    ) -> Any:
        creds = await super().__call__(request)
        if creds is None:
            raise NotAuthenticated()

        token = creds.credentials
        token_data = decode_token(token)

        if token_data is None:
            raise InvalidToken()

        self.verify_token_data(token_data)
        return token_data

    def verify_token_data(self, token_data: dict) -> None:
        raise NotImplementedError("Subclasses must implement verify_token_data")



class AccessTokenBearer(TokenBearer):
    """
    Validates access tokens (stateless — no Redis lookup required).
    Use this as a dependency on any protected route.
    """

    def verify_token_data(self, token_data: dict) -> None:
        if token_data.get("token_type") != "access":
            raise AccessTokenRequired()


class RefreshTokenBearer(TokenBearer):
    """
    Validates refresh tokens and checks the JTI against the Redis allowlist.
    Use this as a dependency on the token-refresh and logout endpoints.
    """

    async def __call__(
        self, request: Request, session: AsyncSession = Depends(get_session),
        user_service: UserService = Depends(get_user_service),
        redis: RedisService = Depends(get_redis),
    ) -> Any:
        # Bypass parent __call__ so we can do the async Redis check ourselves
        creds = await super(HTTPBearer, self).__call__(request)
        if creds is None:
            raise NotAuthenticated()

        token_data = decode_token(creds.credentials)
        if not token_data:
            raise InvalidToken()

        if token_data.get("token_type") != "refresh":
            raise RefreshTokenRequired()

        jti = token_data.get("jti")
        user_id = token_data.get("user", {}).get("user_id")

        if not jti or not user_id:
            raise InvalidToken()

        if not await user_service.is_token_valid(user_id=user_id, jti=jti, redis=redis):
            raise InvalidToken()

        return token_data



async def get_current_user(
    token_details: dict = Depends(AccessTokenBearer()),
    session: AsyncSession = Depends(get_session),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """
    Resolves the authenticated User from an access token.
    Raises typed errors for inactive or unverified accounts.
    """
    user_id = token_details["user"]["user_id"]
    user = await user_service.get_user(user_id, session)

    if not user:
        raise NotAuthenticated()
    if not user.is_active:
        raise UserNotActive()
    if not user.is_email_verified:
        raise AccountNotVerified()

    return user



# Role guard

class RoleChecker:
    """
    Dependency guard that enforces role-based access control.

    Usage::

        @router.get("/admin-only")
        async def admin_route(allowed: bool = Depends(RoleChecker(["admin"]))):
            ...
    """

    def __init__(self, allowed_roles: list[str]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> bool:
        if current_user.role in self.allowed_roles:
            return True
        raise InsufficientPermission()