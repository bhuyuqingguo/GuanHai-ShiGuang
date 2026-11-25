from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


class HistoryStore:
    def __init__(self, limit: int = 100) -> None:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OpticalDesk"
        base.mkdir(parents=True, exist_ok=True)
        self.path = base / "history.json"
        self.limit = limit

    def load(self) -> list[dict[str, str]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError, TypeError):
            return []

    def add(self, operation: str, ok: bool, message: str, forced: bool = False) -> None:
        records = self.load()
        records.insert(0, {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operation": operation,
            "status": "强制结束" if forced else ("成功" if ok else "未完成"),
            "message": message,
            "forced": bool(forced),
        })
        try:
            self.path.write_text(json.dumps(records[: self.limit], ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass
