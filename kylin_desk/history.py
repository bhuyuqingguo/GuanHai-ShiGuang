from __future__ import annotations
import json, os, time
from pathlib import Path
class HistoryStore:
    PATH=Path(os.environ.get("XDG_DATA_HOME",Path.home()/".local/share"))/"GuanHaiShiGuang"/"history.json"
    def load(self):
        try:
            data=json.loads(self.PATH.read_text(encoding="utf-8")); return data if isinstance(data,list) else []
        except (OSError,ValueError):return []
    def add(self,operation,ok,message):
        rows=[{"time":time.strftime("%Y-%m-%d %H:%M:%S"),"operation":operation,"status":"成功" if ok else "失败","message":message}]+self.load()
        self.PATH.parent.mkdir(parents=True,exist_ok=True); self.PATH.write_text(json.dumps(rows[:100],ensure_ascii=False,indent=2),encoding="utf-8")
    def clear(self):
        try:self.PATH.unlink()
        except FileNotFoundError:pass
