from redis import asyncio as aioredis


class RedisService:
    """
    A service for managing user sessions and token blocklists in Redis.
    This service is specific to the authentication context.
    """

    def __init__(self, client: aioredis.Redis):
        self.client = client

    async def add_jti_to_user_sessions(
        self, user_id: str, jti: str, expiry_seconds: int
    ) -> None:
        """Add a JTI to a user's set of active session tokens."""
        key = f"user_sessions:{user_id}"
        await self.client.sadd(key, jti)  # type: ignore
        await self.client.expire(key, expiry_seconds)

    async def remove_jti_from_user_sessions(self, user_id: str, jti: str) -> None:
        """Remove a specific JTI from a user's active sessions."""
        key = f"user_sessions:{user_id}"
        await self.client.srem(key, jti)  # type: ignore

    async def is_jti_in_user_sessions(self, user_id: str, jti: str) -> bool:
        """Check if a JTI exists in a user's active sessions."""
        key = f"user_sessions:{user_id}"
        is_member = await self.client.sismember(key, jti)  # type: ignore
        return bool(is_member)

    async def delete_all_user_sessions(self, user_id: str) -> None:
        """Delete all session tokens for a user (e.g., for 'logout all')."""
        key = f"user_sessions:{user_id}"
        await self.client.delete(key)

    async def get_user_session_count(self, user_id: str) -> int:
        """Get the count of active sessions for a user."""
        key = f"user_sessions:{user_id}"
        count = await self.client.scard(key)  # type: ignore
        return int(count)
