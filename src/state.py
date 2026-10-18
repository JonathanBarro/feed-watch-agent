"""Persistent state: which items were already seen, so each one is reported only once."""

import json
from pathlib import Path

MAX_REMEMBERED_IDS = 5000  # keeps state.json small


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"initialized": False, "seen_ids": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("initialized", False)
    data.setdefault("seen_ids", [])
    return data


def save_state(path: Path, state: dict) -> None:
    state["seen_ids"] = state["seen_ids"][-MAX_REMEMBERED_IDS:]
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
