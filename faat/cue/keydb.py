import json
from pathlib import Path


class KeyDB:
    def __init__(self, path):
        self.path = Path(path)
        self._content = None

    def find(self, name=None):
        if name is None:
            name = "default"
        k = self.content["keys"].get(name)
        return KeyEntry(k["url"], k["key"])

    def add(self, name, url, key):
        new_content = {
            **self.content,
            "keys": {**self.content["keys"], name: {"url": url, "key": key}},
        }
        with self.path.open("w") as f:
            json.dump(new_content, f, indent=2)
            self._content = new_content

    @property
    def content(self):
        if self._content is None:
            try:
                with self.path.open() as f:
                    self._content = json.load(f)
            except (FileNotFoundError, ValueError):
                self._content = {"keys": {}}
        return self._content


class KeyEntry:
    def __init__(self, url, key):
        self.url = url
        self.key = key
