import os
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Generator
from unittest.mock import patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from redis import asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from auth.redis import RedisService
from config import Config
from src.auth.config import auth_settings
from src.auth.schemas import UserCreate


# --- POSTGRES CONTAINER (session-scoped: starts once, shared across all tests) ---
@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15") as postgres:
        yield postgres


# --- REDIS CONTAINER (session-scoped) ---
@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7") as redis:
        yield redis



@pytest.fixture(scope="session", autouse=True)
def set_test_env(postgres_container, redis_container):
    """Override env vars so your Config picks up test containers"""
    sync_url = postgres_container.get_connection_url()
    async_url = sync_url.replace(
        "postgresql+psycopg2://",  # testcontainers adds psycopg2 explicitly
        "postgresql+asyncpg://"
    )
    # Fallback in case it's a plain postgresql:// URL
    if async_url.startswith("postgresql://"):
        async_url = async_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    os.environ["DATABASE_URL"] = async_url
    os.environ["REDIS_URL"] = (
        f"redis://{redis_container.get_container_host_ip()}"
        f":{redis_container.get_exposed_port(6379)}"
    )
    # os.environ["ENVIRONMENT"] = "test"
    yield
    
# --- ASYNC ENGINE (session-scoped, built from container URL) ---
@pytest.fixture(scope="session")
async def async_engine(postgres_container, set_test_env):
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    user = postgres_container.username
    password = postgres_container.password
    db = postgres_container.dbname

    async_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"
    engine = create_async_engine(async_url, echo=True, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()

# --- DB SESSION (function-scoped: fresh session per test) ---

@pytest.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with async_session() as session:
        yield session
        # Clean up committed data after each test
        await session.rollback()
        # Truncate all tables to reset state
        async with async_engine.begin() as conn:
            await conn.execute(text('TRUNCATE TABLE otp, profile, "user" RESTART IDENTITY CASCADE'))
        
@pytest.fixture(scope="session")
async def async_client(async_engine, set_test_env) -> AsyncGenerator[AsyncClient, None]:
    from src.db.database import get_session
    from src.limiter import limiter
    from src.main import app
    
    limiter.enabled = False

    # Override the get_session dependency so the APP uses the SAME engine as tests
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async_session = async_sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    limiter.enabled = True  # restore after session
    app.dependency_overrides.clear()

@pytest.fixture(scope="session")
def app_instance(async_engine, set_test_env):
    from src.db.database import get_session
    from src.main import app

    async def override_get_session():
        async_session = async_sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    return app  # ← expose the app object directly

@pytest.fixture
def redis(app_instance) -> RedisService:
    return app_instance.state.redis

@pytest.fixture(autouse=True)
async def setup_redis(app_instance):  # ← use app_instance, not async_client
    redis_client = aioredis.from_url(
        Config.REDIS_URL, encoding="utf-8", decode_responses=True
    )
    app_instance.state.redis = RedisService(redis_client)
    yield
    await redis_client.flushdb()
    await redis_client.aclose()
    
# --- REDIS CLIENT (function-scoped: flush after each test) ---
@pytest.fixture(scope="function")
def redis_client(redis_container):
    import redis
    client = redis.Redis(
        host=redis_container.get_container_host_ip(),
        port=redis_container.get_exposed_port(6379),
        decode_responses=True
    )
    yield client
    client.flushall()  # wipe all data after each test
    
# tests/conftest.py
# @pytest.fixture(scope="session")
# def celery_app():
#     from src.celery_app import celery  # your celery instance
#     celery.conf.update(
#         task_always_eager=True,       # run tasks inline
#         task_eager_propagates=True,   # surface exceptions
#     )
#     return celery

# ── User data fixtures ─---

@pytest.fixture
def valid_user_data():
    return {
        "email": "test@example.com",
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User",
        "password": "SecurePass123!",
    }


@pytest.fixture
def another_user_data():
    """
    Used in tests that need a second distinct user (e.g. test_password_is_hashed).
    Different email/username from valid_user_data to avoid conflicts.
    """
    return {
        "email": "another@example.com",
        "username": "anotheruser",
        "first_name": "Another",
        "last_name": "User",
        "password": "SecurePass123!",
    }


@pytest.fixture
def user2_data():
    return {
        "email": "user2@example.com",
        "username": "user2",
        "first_name": "Test",
        "last_name": "User2",
        "password": "SecurePass123!",
    }


@pytest.fixture
def user3_data():
    return {
        "email": "user3@example.com",
        "username": "user3",
        "first_name": "Test",
        "last_name": "User3",
        "password": "SecurePass123!",
    }


@pytest.fixture
def invalid_user_data():
    """
    Used in test_register_invalid_email.
    The email field contains a clearly invalid format.
    """
    return {
        "email": "not-an-email",
        "username": "invaliduser",
        "first_name": "Invalid",
        "last_name": "User",
        "password": "SecurePass123!",
    }


@pytest.fixture
def weak_password_data():
    """
    Used in test_register_weak_password.
    Password is too short and has no special chars — should fail validation.
    """
    return {
        "email": "weakpass@example.com",
        "username": "weakpassuser",
        "first_name": "Weak",
        "last_name": "Pass",
        "password": "123",
    }
    
# ── User fixtures (DB) ──

@pytest.fixture
def mock_otp() -> int:
    return 123456  # must be int to match Otp.otp: int

@pytest.fixture
def mock_email() -> Generator[list, None, None]:
    """
    Captures all emails sent during a test.
    Patches src.auth.service.send_email to capture emails instead of actually sending.
    """
    sent_emails = []

    def fake_send_email(_background_tasks, subject, email_to, template_context, template_name):
        # Just capture the email, don't actually send
        sent_emails.append({
            "email_to": email_to,
            "subject": subject,
            "template_name": template_name,
            "template_context": template_context,
        })

    with patch("src.mail.send_email", fake_send_email):
        yield sent_emails
        
@pytest.fixture
async def registered_user(
    db_session: AsyncSession,
    user2_data: dict,
):
    from src.auth.service import UserService
    user_service = UserService()
    user_create = UserCreate(**user2_data)
    user = await user_service.create_user(user_create, db_session)
    return user


@pytest.fixture
async def verified_user(
    db_session: AsyncSession,
    user3_data: dict,
):
    from src.auth.service import UserService
    user_service = UserService()
    user_create = UserCreate(**user3_data)
    user = await user_service.create_user(user_create, db_session)
    await user_service.update_user(user, {"is_email_verified": True}, db_session)
    return user


@pytest.fixture
async def another_verified_user(
    db_session: AsyncSession,
    valid_user_data: dict,
):
    from src.auth.service import UserService
    user_service = UserService()
    user_create = UserCreate(**valid_user_data)
    user = await user_service.create_user(user_create, db_session)
    await user_service.update_user(user, {"is_email_verified": True}, db_session)
    return user


@pytest.fixture
async def inactive_user(
    db_session: AsyncSession,
    another_user_data: dict,
):
    from src.auth.service import UserService
    user_service = UserService()
    user_create = UserCreate(**another_user_data)
    user = await user_service.create_user(user_create, db_session)
    await user_service.update_user(
        user, {"is_email_verified": True, "is_active": False}, db_session
    )
    return user


@pytest.fixture
async def otp_for_user(
    db_session: AsyncSession,
    registered_user,
    mock_otp: int,  # int, not str
):
    from src.db.models import Otp
    otp_record = Otp(user_id=registered_user.id, otp=mock_otp)  # type: ignore
    db_session.add(otp_record)
    await db_session.commit()
    return mock_otp

# ── Token fixtures 


@pytest.fixture
def expired_refresh_token():
    now = datetime.now(timezone.utc)
    user_data = {
        "user": {
            "email": "test@example.com",
            "user_id": "test-user-id",
            "role": "user",
        },
        "iat": now,
        "exp": now - timedelta(hours=1),  # Already expired
        "jti": "expired-token-jti",
        "token_type": "refresh",
    }
    return jwt.encode(user_data, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALGORITHM)


@pytest.fixture
def expired_access_token():
    now = datetime.now(timezone.utc)
    user_data = {
        "user": {
            "email": "test@example.com",
            "user_id": "test-user-id",
            "role": "user",
        },
        "iat": now,
        "exp": now - timedelta(minutes=30),  # Already expired
        "jti": "expired-access-token-jti",
        "token_type": "access",
    }
    return jwt.encode(user_data, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALGORITHM)
