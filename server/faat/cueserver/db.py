from . import settings
from .apikeydb import ApiKeyDB
from redis.asyncio import Redis

redis_db = Redis.from_url(str(settings.REDIS_URL), decode_responses=True)
apikey_db = ApiKeyDB(redis_db)
