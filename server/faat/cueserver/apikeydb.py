import hashlib
import json
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

    async def start_key_request(self, name):
        apikey = secrets.token_urlsafe()
        h = hashlib.sha256(apikey.encode()).hexdigest()
        while True:
            request_id = create_request_id()
            payload = json.dumps({"name": name, "h": h})
            is_set = await self.r.set(f"key-rq:{request_id}", payload, ex=10 * 60, nx=True)
            if is_set:
                return request_id, apikey

    async def find_key_request(self, request_id):
        is_valid_id = len(request_id) > 5 and request_id.isalnum()
        if not is_valid_id:
            return None
        payload = await self.r.get(f"key-rq:{request_id}")
        if payload is None:
            return None
        return json.loads(payload)

    async def redeem_key_request(self, request_id, uid, name):
        is_valid_id = len(request_id) > 5 and request_id.isalnum()
        if not is_valid_id:
            raise ValueError("Invalid ID")

        payload = json.loads(await self.r.get(f"key-rq:{request_id}"))
        if payload is None:
            raise ValueError("Unknown ID")

        h = payload["h"]
        key_details = {"uid": uid, "date": time.time(), "name": name}
        async with self.r.pipeline(transaction=True) as pipe:
            await (
                pipe.set(f"apikey:{h}", json.dumps(key_details))
                .set(f"apikey:{h}:uid", uid)
                .sadd(f"user:{uid}:apikeys", h)
                .execute()
            )

    async def get_token_user(self, apikey):
        h = hashlib.sha256(apikey.encode()).hexdigest()
        uid = await self.r.get(f"apikey:{h}:uid")
        return uid

    async def find_user_apikeys(self, uid):
        return [
            json.loads(await self.r.get(f"apikey:{h}"))
            for h in await self.r.smembers(f"user:{uid}:apikeys")
        ]

    async def close(self):
        await self.r.close()


def create_request_id(size=20):
    sr = random.SystemRandom()
    return "".join(sr.choice(REQUEST_ID_ALPHABET) for _ in range(size))


REQUEST_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
