from typing import List

from fastapi.responses import RedirectResponse
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.schemas import UserCreate, UserCreateOAuth
from src.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)
from src.config import Config
from src.db.models import Otp, Profile, User
from src.db.redis import (
    add_jti_to_user_sessions,
    delete_all_user_sessions,
    is_jti_in_user_sessions,
    remove_jti_from_user_sessions,
)
from src.errors import UserNotActive


class UserService:
    async def get_user(self, user_id: str, session: AsyncSession):
        statement = (
            select(User).where(User.id == user_id).options(selectinload(User.profile))  # type: ignore
        )
        result = await session.exec(statement)
        user = result.first()
        return user

    async def get_user_by_email(self, email: str, session: AsyncSession):
        statement = select(User).where(User.email == email)
        result = await session.exec(statement)
        user = result.first()
        return user

    async def get_user_by_username(self, username: str, session: AsyncSession):
        statement = select(User).where(User.username == username)
        result = await session.exec(statement)
        user = result.first()
        return user

    async def get_otp_by_user(self, user_id: str, otp: int, session: AsyncSession):
        statement = select(Otp).where(Otp.user_id == user_id, Otp.otp == otp)
        result = await session.exec(statement)
        otp_record = result.first()
        return otp_record

    async def get_user_otps(self, user_id: str, session: AsyncSession) -> List[Otp]:
        statement = select(Otp).where(Otp.user_id == user_id)
        result = await session.exec(statement)
        return list(result.all())

    async def user_exists(self, email: str, session: AsyncSession):
        user = await self.get_user_by_email(email, session)
        return user is not None

    async def username_exists(self, username: str, session: AsyncSession):
        user = await self.get_user_by_username(username, session)
        return user is not None

    async def create_user(self, user_data: UserCreate, session: AsyncSession):
        extra_data = {
            "hashed_password": hash_password(user_data.password),
        }

        new_user = User.model_validate(user_data, update=extra_data)

        session.add(new_user)

        await session.commit()
        await session.refresh(new_user)

        profile = Profile(user_id=new_user.id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)

        return new_user

    async def create_oauth_user(
        self, user_data: UserCreateOAuth, session: AsyncSession
    ):

        new_user = User.model_validate(user_data)

        new_user.is_email_verified = True

        session.add(new_user)

        await session.commit()
        await session.refresh(new_user)

        profile = Profile(user_id=new_user.id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)

        return new_user

    async def handle_oauth_user_login(self, user: User, session: AsyncSession) -> dict:
        """
        Handle OAuth user login, ensuring email verification and active status.

        Args:
            user: The authenticated user from OAuth provider
            session: Database session

        Returns:
            dict: Token pair (access_token, refresh_token)

        Raises:
            UserNotActive: If user account is disabled
        """
        if not user.is_email_verified:
            user.is_email_verified = True
            session.add(user)
            await session.commit()
            await session.refresh(user)

        if not user.is_active:
            raise UserNotActive()

        # login user
        user_data = {
            "email": user.email,
            "user_id": str(user.id),
            "role": user.role.value,
        }

        return await self.create_token_pair(user_data, session)

    async def handle_oauth_user_register(
        self, user_create_data: UserCreateOAuth, session: AsyncSession
    ) -> tuple[User, RedirectResponse]:
        new_user = await self.create_oauth_user(user_create_data, session)

        user_data = {
            "email": new_user.email,
            "user_id": str(new_user.id),
            "role": new_user.role.value,
        }

        tokens = await self.create_token_pair(user_data, session)
        access = tokens["access"]
        refresh = tokens["refresh"]

        frontend_callback_url = Config.FRONTEND_CALLBACK_URL
        redirect_url = (
            f"{frontend_callback_url}" f"?access={access}&refresh={refresh}&is_new=true"
        )

        response = RedirectResponse(redirect_url)
        # response.set_cookie(
        #     key="refresh",
        #     value=refresh,
        #     httponly=True,
        #     secure=True,  # Ensure you're using HTTPS
        #     samesite="None",
        # )

        return new_user, response

    async def update_user(self, user: User, user_data: dict, session: AsyncSession):
        for k, v in user_data.items():
            setattr(user, k, v)

        await session.commit()
        return user

    async def create_token_pair(self, user_data: dict, _: AsyncSession) -> dict:
        """Create both access and refresh tokens"""
        refresh_token = create_refresh_token(user_data)

        refresh_payload = decode_token(refresh_token)
        if not refresh_payload:
            raise Exception("Failed to decode recently created token")

        refresh_jti = refresh_payload["jti"]
        # expires_at = datetime.fromtimestamp(refresh_payload["exp"])

        # Add JTI to user's active sessions in Redis
        await add_jti_to_user_sessions(
            user_id=str(user_data["user_id"]),
            jti=refresh_jti,
            expiry_seconds=7776000,  # 90 days
        )

        access_token = create_access_token(user_data)

        return {
            "access": access_token,
            "refresh": refresh_token,
        }

    async def revoke_user_token(self, user_id: str, jti: str) -> None:
        """Remove a JTI from user's active sessions (logout single device)"""
        await remove_jti_from_user_sessions(user_id=user_id, jti=jti)

    async def revoke_all_user_tokens(self, user_id: str) -> None:
        """Delete all active sessions for a user (logout all devices)"""
        await delete_all_user_sessions(user_id=user_id)

    async def is_token_valid(self, user_id: str, jti: str) -> bool:
        """Check if a refresh token JTI is in the user's active sessions"""
        return await is_jti_in_user_sessions(user_id=user_id, jti=jti)
