import hashlib
import json
import random
import secrets
import time
import uuid


class ApiKeyDB:
    def __init__(self, r):
        self.r = r

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start_key_request(self, name, pattern):
        apikey = secrets.token_urlsafe()
        h = hashlib.sha256(apikey.encode()).hexdigest()
        while True:
            request_id = create_request_id()
            key_id = str(uuid.uuid4())
            payload = json.dumps({"keyId": key_id, "name": name, "pattern": pattern, "h": h})
            is_set = await self.r.set(f"key-rq:{request_id}", payload, ex=5 * 60, nx=True)
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
        key_details = {
            "id": payload["keyId"],
            "uid": uid,
            "date": time.time(),
            "name": name,
            "pattern": payload["pattern"],
            "h": h,
        }
        async with self.r.pipeline(transaction=True) as pipe:
            await (
                pipe.set(f"keyhash:{h}", json.dumps(key_details))
                .set(f"apikey:{key_details['id']}", json.dumps(key_details))
                .sadd(f"user:{uid}:apikeys", key_details["id"])
                .execute()
            )

    async def get_key(self, apikey):
        h = hashlib.sha256(apikey.encode()).hexdigest()
        payload = await self.r.get(f"keyhash:{h}")
        if payload is None:
            return None
        return json.loads(payload)

    async def find_user_apikeys(self, uid):
        key_ids = await self.r.smembers(f"user:{uid}:apikeys")
        if not key_ids:
            return []
        z = [f"apikey:{key_id}" for key_id in key_ids]
        return [json.loads(k) for k in await self.r.mget(z)]

    async def remove_key(self, key_id):
        payload = await self.r.get(f"apikey:{key_id}")
        if not payload:
            return None
        key = json.loads(payload)
        h = key["h"]
        uid = key["uid"]
        async with self.r.pipeline(transaction=True) as pipe:
            await (
                pipe.delete(f"keyhash:{h}", f"apikey:{key_id}")
                .srem(f"user:{uid}:apikeys", key_id)
                .execute()
            )

    async def close(self):
        await self.r.close()


def create_request_id(size=20):
    sr = random.SystemRandom()
    return "".join(sr.choice(REQUEST_ID_ALPHABET) for _ in range(size))


REQUEST_ID_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
