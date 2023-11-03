from starlette.config import Config
from starlette.datastructures import Secret

config = Config(".env")

DEBUG = config("DEBUG", cast=bool, default=False)

SESSION_SECRET_KEY = config("SESSION_SECRET_KEY", cast=Secret)
SESSION_HTTPS_ONLY = config("SESSION_HTTPS_ONLY", cast=bool, default=True)

REDIS_URL = config("REDIS_URL", cast=Secret)
