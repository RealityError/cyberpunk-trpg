import json
from pathlib import Path
from threading import RLock
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHARACTERS_FILE = DATA_DIR / "characters.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"

_lock = RLock()


def read_json(path: Path, default: Any) -> Any:
    with _lock:
        if not path.exists():
            return default

        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return default

        return json.loads(raw)


def write_json(path: Path, data: Any) -> None:
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        tmp_path.write_text(payload + "\n", encoding="utf-8")
        tmp_path.replace(path)
