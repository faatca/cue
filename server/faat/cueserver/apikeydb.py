import hashlib
import random
import secrets
import time


class ApiKeyDB:
    def __init__(self, r):
        self.r = r

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start_key_request(self):
        apikey = secrets.token_urlsafe()
        h = hashlib.sha256(apikey.encode()).hexdigest()
        while True:
            request_id = create_request_id()
            is_set = await self.r.set(f"key-rq:{request_id}", h, ex=10 * 60, nx=True)
            if is_set:
                return request_id, apikey

    async def is_valid_key_request(self, request_id):
        is_valid_id = len(request_id) > 5 and request_id.isalnum()
        if not is_valid_id:
            return False
        h = await self.r.get(f"key-rq:{request_id}")
        return h is not None

    async def redeem_key_request(self, request_id, uid, name):
        is_valid_id = len(request_id) > 5 and request_id.isalnum()
        if not is_valid_id:
            raise ValueError("Invalid ID")
        h = await self.r.get(f"key-rq:{request_id}")
        if h is None:
            raise ValueError("Unknown ID")

        async with self.r.pipeline(transaction=True) as pipe:
            await (
                pipe.set(f"apikey:{h}:uid", uid)
                .set(f"apikey:{h}:date", time.time())
                .set(f"apikey:{h}:name", name)
                .sadd(f"user:{uid}:apikeys", h)
                .execute()
            )

    async def get_token_user(self, apikey):
        h = hashlib.sha256(apikey.encode()).hexdigest()
        uid = await self.r.get(f"apikey:{h}:uid")
        return uid

    async def find_user_apikeys(self, uid):
        return [
            await self.r.get(f"apikey:{h}:name")
            for h in await self.r.smembers(f"user:{uid}:apikeys")
        ]

    async def close(self):
        await self.r.close()


def create_request_id(size=20):
    sr = random.SystemRandom()
    return "".join(sr.choice(REQUEST_ID_ALPHABET) for _ in range(size))


REQUEST_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
