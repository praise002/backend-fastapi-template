from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import Config

# Ensure DATABASE_URL is set before creating the engine
if Config.DATABASE_URL is None:
    raise ValueError(
        "DATABASE_URL must be set in environment or assembled from POSTGRES_* variables"
    )

async_engine = create_async_engine(url=Config.DATABASE_URL, echo=True)


async def init_db():
    async with async_engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all)

        await conn.run_sync(
            SQLModel.metadata.create_all
        )  # used sync cos it doesn't execute asynchronously


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
