from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RunHistoryStore:
    def __init__(self, base_dir: str = "data") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _user_path(self, username: str) -> Path:
        # Sanitize username for filesystem safety
        safe_username = "".join(c for c in username if c.isalnum() or c in "_-")
        path = self.base_dir / f"runs_{safe_username}.jsonl"
        path.touch(exist_ok=True)
        return path

    def record_run(
        self,
        username: str,
        *,
        finished_at: str,
        company_name: str,
        valuation: float,
        reputation: float,
        compliance: float,
        score: float,
        status: str,
    ) -> None:
        item = {
            "finished_at": finished_at,
            "company_name": company_name,
            "valuation": valuation,
            "reputation": reputation,
            "compliance": compliance,
            "score": score,
            "status": status,
        }
        path = self._user_path(username)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=True) + "\n")

    def latest_runs(self, username: str, limit: int = 15) -> list[dict[str, Any]]:
        if limit <= 0:
            return []

        path = self._user_path(username)
        with path.open("r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        rows: list[dict[str, Any]] = []
        for line in reversed(lines):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(rows) >= limit:
                break

        return rows
