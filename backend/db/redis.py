from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

redis_pool: ArqRedis = None


async def create_redis_pool():
    global redis_pool
    redis_pool = await create_pool(RedisSettings())
