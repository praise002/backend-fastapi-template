from redis import asyncio as aioredis

from src.config import Config

token_blocklist = aioredis.from_url(Config.REDIS_URL)


async def add_jti_to_user_sessions(user_id: str, jti: str, expiry_seconds: int) -> None:
    """Add a JTI to user's active sessions set"""
    key = f"user_sessions:{user_id}"
    await token_blocklist.sadd(key, jti)  # type: ignore
    await token_blocklist.expire(key, expiry_seconds)  # Set expiry on the set


async def remove_jti_from_user_sessions(user_id: str, jti: str) -> None:
    """Remove a specific JTI from user's sessions"""
    key = f"user_sessions:{user_id}"
    await token_blocklist.srem(key, jti)  # type: ignore


async def is_jti_in_user_sessions(user_id: str, jti: str) -> bool:
    """Check if JTI exists in user's active sessions"""
    key = f"user_sessions:{user_id}"
    return await token_blocklist.sismember(key, jti)  # type: ignore


async def delete_all_user_sessions(user_id: str) -> None:
    """Delete all sessions for a user (logout all)"""
    key = f"user_sessions:{user_id}"
    await token_blocklist.delete(key)


async def get_user_session_count(user_id: str) -> int:
    """Get count of active sessions for a user"""
    key = f"user_sessions:{user_id}"
    return await token_blocklist.scard(key)  # type: ignore


