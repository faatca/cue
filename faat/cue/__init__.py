import logging
from pathlib import Path

from .cueclient import CueClient, AsyncCueClient
from .errors import ConfigurationError
from .keydb import KeyDB

__version__ = "0.5.1"

log = logging.getLogger(__name__)


def connect(config_path=None, key_name=None, url=None, key=None):
    if config_path is None:
        config_path = Path.home() / ".config/cue.json"

    if key_name is None:
        key_name = "default"

    if url is None or key is None:
        k = KeyDB(config_path).find(key_name)
        if k is None:
            raise ConfigurationError("Authentication required")
        url = url or k.url
        key = key or k.key

    return CueClient(url, key)


def connect_async(config_path=None, key_name=None, url=None, key=None):
    if config_path is None:
        config_path = Path.home() / ".config/cue.json"

    if key_name is None:
        key_name = "default"

    if url is None or key is None:
        k = KeyDB(config_path).find(key_name)
        if k is None:
            raise ConfigurationError("Authentication required")
        url = url or k.url
        key = key or k.key

    return AsyncCueClient(url, key)
