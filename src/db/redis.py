
from redis import asyncio as aioredis

from src.config import Config

_token_blocklist = None


async def get_token_blocklist():
    """Get or create the token blocklist Redis client (lazy initialization)"""
    global _token_blocklist
    if _token_blocklist is None:
        _token_blocklist = aioredis.from_url(Config.REDIS_URL)
    return _token_blocklist


async def add_jti_to_user_sessions(user_id: str, jti: str, expiry_seconds: int) -> None:
    """Add a JTI to user's active sessions set"""
    token_blocklist = await get_token_blocklist()
    key = f"user_sessions:{user_id}"
    await token_blocklist.sadd(key, jti)  
    await token_blocklist.expire(key, expiry_seconds)  # Set expiry on the set


async def remove_jti_from_user_sessions(user_id: str, jti: str) -> None:
    """Remove a specific JTI from user's sessions"""
    token_blocklist = await get_token_blocklist()
    key = f"user_sessions:{user_id}"
    await token_blocklist.srem(key, jti)  


async def is_jti_in_user_sessions(user_id: str, jti: str) -> bool:
    """Check if JTI exists in user's active sessions"""
    token_blocklist = await get_token_blocklist()
    key = f"user_sessions:{user_id}"
    return await token_blocklist.sismember(key, jti) 


async def delete_all_user_sessions(user_id: str) -> None:
    """Delete all sessions for a user (logout all)"""
    token_blocklist = await get_token_blocklist()
    key = f"user_sessions:{user_id}"
    await token_blocklist.delete(key)


async def get_user_session_count(user_id: str) -> int:
    """Get count of active sessions for a user"""
    token_blocklist = await get_token_blocklist()
    key = f"user_sessions:{user_id}"
    return await token_blocklist.scard(key)  
