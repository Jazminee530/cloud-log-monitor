from redis import Redis
from rq import Queue

from app.config import REDIS_URL


def get_redis() -> Redis:
    return Redis.from_url(REDIS_URL)


def get_queue() -> Queue:
    # JSON avoids deserializing untrusted pickle payloads.
    return Queue("logs", connection=get_redis(), serializer="json")
