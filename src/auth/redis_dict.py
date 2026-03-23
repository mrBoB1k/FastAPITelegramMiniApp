import redis.asyncio as redis
from config import REDIS_HOST, REDIS_PORT


class RedisUserVersionDict:
    def __init__(self):
        self.redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=0,
            decode_responses=True
        )

        # Lua скрипт для compare_version
        self.compare_script = self.redis.register_script("""
        local key = KEYS[1]
        local version = tonumber(ARGV[1])

        local current = redis.call("GET", key)

        if not current then
            redis.call("SET", key, version + 1)
            return 0
        end

        if tonumber(current) == version then
            return 1
        end

        return 0
        """)

        self.increment_script = self.redis.register_script("""
        local key = KEYS[1]

        if redis.call("EXISTS", key) == 1 then
            return redis.call("INCR", key)
        end

        return nil
        """)

    def _key(self, participant_id: int) -> str:
        return f"user_version:{participant_id}"

    async def get_or_create(self, participant_id: int) -> int:
        key = self._key(participant_id)

        value = await self.redis.get(key)

        if value is None:
            await self.redis.set(key, 0)
            return 0

        return int(value)

    async def get(self, participant_id: int) -> int | None:
        key = self._key(participant_id)

        value = await self.redis.get(key)

        if value is None:
            return None

        return int(value)

    async def compare_version(self, participant_id: int, user_version: int) -> bool:
        key = self._key(participant_id)

        result = await self.compare_script(
            keys=[key],
            args=[user_version]
        )

        return bool(result)

    async def increment(self, participant_id: int) -> None:
        key = self._key(participant_id)
        await self.increment_script(keys=[key])

    async def delete(self, participant_id: int) -> None:
        key = self._key(participant_id)
        await self.redis.delete(key)


redis_dict = RedisUserVersionDict()
