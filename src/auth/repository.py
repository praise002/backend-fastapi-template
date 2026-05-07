"""
Repository Layer (Data Adapter)
================================
Implements all data access and mutation operations against the database.
Uses SQLModel/ORM only — no business logic, no HTTP concerns.

Dependency direction: inward only.
  - Imports from: domain/schemas, infrastructure/security
  - Must NOT import from: services, controllers, routers

Each public method maps to a CRUD operation or a focused query.
Complex orchestration (e.g. create user + create profile + send email)
belongs in the service layer, not here.
"""
import random
from typing import List

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.schemas import UserCreate, UserCreateOAuth
from src.auth.security import hash_password
from src.db.models import Otp, Profile, User


class UserRepository:
    """CRUD operations for the User model."""

    async def get_by_id(self, user_id: str, session: AsyncSession) -> User | None:
        statement = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.profile))  # type: ignore
        )
        result = await session.exec(statement)
        return result.first()

    async def get_by_email(self, email: str, session: AsyncSession) -> User | None:
        result = await session.exec(select(User).where(User.email == email))
        return result.first()

    async def get_by_username(
        self, username: str, session: AsyncSession
    ) -> User | None:
        result = await session.exec(select(User).where(User.username == username))
        return result.first()

    async def create(self, user_data: UserCreate, session: AsyncSession) -> User:
        """Create a standard (email/password) user with a linked Profile."""
        extra = {"hashed_password": hash_password(user_data.password)}
        new_user = User.model_validate(user_data, update=extra)

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        # Always initialise an empty profile alongside the user
        profile = Profile(user_id=new_user.id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)

        return new_user

    async def create_oauth(
        self, user_data: UserCreateOAuth, session: AsyncSession
    ) -> User:
        """Create an OAuth user. Email is pre-verified by the provider."""
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

    async def update(
        self, user: User, data: dict, session: AsyncSession
    ) -> User:
        """Apply a partial update dict to a user and persist it."""
        for key, value in data.items():
            setattr(user, key, value)
        await session.commit()
        return user

    async def exists_by_email(self, email: str, session: AsyncSession) -> bool:
        return await self.get_by_email(email, session) is not None

    async def exists_by_username(self, username: str, session: AsyncSession) -> bool:
        return await self.get_by_username(username, session) is not None


class OtpRepository:
    """CRUD operations for the Otp model."""

    async def get_by_user_and_code(
        self, user_id: str, otp: int, session: AsyncSession
    ) -> Otp | None:
        statement = select(Otp).where(Otp.user_id == user_id, Otp.otp == otp)
        result = await session.exec(statement)
        return result.first()

    async def list_by_user(
        self, user_id: str, session: AsyncSession
    ) -> List[Otp]:
        result = await session.exec(select(Otp).where(Otp.user_id == user_id))
        return list(result.all())

    async def create(self, user_id: str, session: AsyncSession) -> int:
        """Generate, persist, and return a new 6-digit OTP value."""
        otp_value = random.randint(100_000, 999_999)
        otp = Otp(user_id=user_id, otp=otp_value) # type: ignore
        session.add(otp)
        await session.commit()
        await session.refresh(otp)
        return otp.otp

    async def invalidate_all(self, user_id: str, session: AsyncSession) -> None:
        """Delete all OTP records for a user (used after consumption or re-issue)."""
        otps = await self.list_by_user(user_id, session)
        for otp in otps:
            await session.delete(otp)
        await session.commit()