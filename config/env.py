import os
from dotenv import load_dotenv
load_dotenv()

def get_env(key: str, default=None):
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f'Missing required environment variable: {key}')

    return value

def get_bool(key: str, default=False):
    value = os.getenv(key, default)
    if value is None:
        return default
    return value.lower() == "true"