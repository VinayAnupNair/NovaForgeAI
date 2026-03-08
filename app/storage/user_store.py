from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict


class UserStore:
    def __init__(self, file_path: str = "data/users.json") -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _load(self) -> Dict[str, str]:
        """Returns {username: password_hash}"""
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: Dict[str, str]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def create_user(self, username: str, password: str) -> bool:
        """Returns True if created, False if username exists"""
        users = self._load()
        if username in users:
            return False
        users[username] = self._hash_password(password)
        self._save(users)
        return True

    def verify_user(self, username: str, password: str) -> bool:
        """Returns True if credentials match"""
        users = self._load()
        if username not in users:
            return False
        return users[username] == self._hash_password(password)

    def user_exists(self, username: str) -> bool:
        users = self._load()
        return username in users
