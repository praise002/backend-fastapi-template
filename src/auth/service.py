"""
Service Layer
=============
Orchestrates business logic by combining repositories (data access) and
providers (external systems). This is where the "what happens" lives —
not "how to store" (repository) and not "how to respond" (controller).

Dependency direction: inward only.
  - Imports from: domain/schemas, repositories, infrastructure
  - Must NOT import from: controllers, routers, FastAPI request/response types

Each method represents a self-contained business operation. Controllers call
these methods and convert the results into HTTP responses.
"""

from src.auth.errors import UserNotActive
from src.auth.redis import RedisService
from src.auth.repository import OtpRepository, UserRepository
from src.auth.schemas import UserCreate, UserCreateOAuth
from src.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from src.db.models import User

# Shared repository instances (stateless, safe to share)

_user_repo = UserRepository()
_otp_repo = OtpRepository()

# Redis TTL matching REFRESH_TOKEN_EXPIRY config (90 days in seconds)
_REFRESH_TTL_SECONDS = 7_776_000


class UserService:
    """
    Orchestrates user-related business operations.

    Depends inward on UserRepository / OtpRepository for data access and
    on infrastructure/security for token creation. Returns domain objects
    or plain dicts — never FastAPI Response objects (that's the controller's job).
    """
    
   

    # ------------------------------------------------------------------
    # Queries (read-only)
    # ------------------------------------------------------------------

    async def get_user(self, user_id: str, session) -> User | None:
        return await _user_repo.get_by_id(user_id, session)

    async def get_user_by_email(self, email: str, session) -> User | None:
        return await _user_repo.get_by_email(email, session)

    async def get_otp_by_user(self, user_id: str, otp: int, session):
        return await _otp_repo.get_by_user_and_code(user_id, otp, session)
    
    async def get_user_otps(self, user_id: str, session):
        return await _otp_repo.list_by_user(user_id, session)

    async def user_exists(self, email: str, session) -> bool:
        return await _user_repo.exists_by_email(email, session)

    async def username_exists(self, username: str, session) -> bool:
        return await _user_repo.exists_by_username(username, session)

    # ------------------------------------------------------------------
    # OTP operations
    # ------------------------------------------------------------------

    async def generate_otp(self, user: User, session) -> int:
        """Invalidate any previous OTPs then create and return a fresh one."""
        await _otp_repo.invalidate_all(str(user.id), session)
        return await _otp_repo.create(str(user.id), session)

    async def invalidate_otps(self, user: User, session) -> None:
        await _otp_repo.invalidate_all(str(user.id), session)

    # ------------------------------------------------------------------
    # User mutations
    # ------------------------------------------------------------------

    async def create_user(self, user_data: UserCreate, session) -> User:
        return await _user_repo.create(user_data, session)

    async def update_user(self, user: User, data: dict, session) -> User:
        return await _user_repo.update(user, data, session)

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    async def create_token_pair(self,  user_data: dict,  _session, redis: RedisService) -> dict:
        """
        Issue a new access + refresh token pair and register the refresh
        token's JTI in the Redis allowlist.
        """
        refresh_token = create_refresh_token(user_data)
        refresh_payload = decode_token(refresh_token)

        if not refresh_payload:
            raise RuntimeError("Failed to decode newly-created refresh token")

        await redis.add_jti_to_user_sessions(
            user_id=str(user_data["user_id"]),
            jti=refresh_payload["jti"],
            expiry_seconds=_REFRESH_TTL_SECONDS,
        )

        return {
            "access": create_access_token(user_data),
            "refresh": refresh_token,
        }

    async def revoke_token(self, user_id: str, jti: str, redis: RedisService) -> None:
        """Remove a single refresh token JTI (single-device logout)."""
        await redis.remove_jti_from_user_sessions(user_id=user_id, jti=jti)

    async def revoke_all_tokens(self, user_id: str, redis: RedisService) -> None:
        """Remove all refresh token JTIs (logout from all devices)."""
        await redis.delete_all_user_sessions(user_id=user_id)

    async def is_token_valid(self, user_id: str, jti: str, redis: RedisService) -> bool:
        return await redis.is_jti_in_user_sessions(user_id=user_id, jti=jti)

    
    # OAuth flows

    async def handle_oauth_login(self, user: User, session, redis: RedisService) -> dict:
        """
        Process login for a returning OAuth user.

        Ensures the user account is verified and active, then issues tokens.
        Returns a token-pair dict — the controller decides how to deliver it.
        """
        if not user.is_email_verified:
            await _user_repo.update(user, {"is_email_verified": True}, session)

        if not user.is_active:
            raise UserNotActive()

        user_data = {
            "email": user.email,
            "user_id": str(user.id),
            "role": user.role.value,
        }
        return await self.create_token_pair(user_data, session, redis)

    async def handle_oauth_register(
        self, user_create_data: UserCreateOAuth, session, redis: RedisService
    ) -> tuple[User, dict]:
        """
        Register a new OAuth user.

        Returns the new User and a token-pair dict.
        The controller is responsible for building the redirect response.
        """
        new_user = await _user_repo.create_oauth(user_create_data, session)

        user_data = {
            "email": new_user.email,
            "user_id": str(new_user.id),
            "role": new_user.role.value,
        }
        tokens = await self.create_token_pair(user_data, session, redis)
        return new_user, tokens
    
