"""Tamper-evident audit log. Each entry carries the hash of the previous one, so edits or deletions break the chain."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

GENESIS = "0" * 64


def _digest(prev_hash: str, body: dict) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    entries: int
    first_bad_line: int | None = None


class AuditLog:
    def __init__(self, path: str | Path, clock=lambda: datetime.now(UTC)):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._lock = threading.Lock()
        self._last_hash = self._read_last_hash()

    def record(self, event: str, **fields) -> dict:
        with self._lock:
            body = {"ts": self._clock().isoformat(), "event": event, **fields}
            entry = {**body, "prev_hash": self._last_hash, "hash": _digest(self._last_hash, body)}
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")
            self._last_hash = entry["hash"]
            return entry

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def verify(self) -> VerifyResult:
        prev = GENESIS
        entries = self.entries()
        for i, entry in enumerate(entries, start=1):
            body = {k: v for k, v in entry.items() if k not in ("prev_hash", "hash")}
            if entry.get("prev_hash") != prev or entry.get("hash") != _digest(prev, body):
                return VerifyResult(False, len(entries), first_bad_line=i)
            prev = entry["hash"]
        return VerifyResult(True, len(entries))

    def _read_last_hash(self) -> str:
        entries = self.entries()
        return entries[-1]["hash"] if entries else GENESIS
