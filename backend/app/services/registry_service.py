"""Minimal file-backed Threat Pattern Registry.

Stores schema-validated, zero-PII-verified threat pattern objects as JSONL
(one envelope per line) with an in-memory index by ``pattern_id``. This is
the smallest useful registry: durable across restarts, inspectable with any
text tool, trivially replaced by a relational store post-MVP.

Validation (schema gate + PII guard) happens in the route layer *before*
``add()`` is called; the registry trusts nothing else and re-checks only
uniqueness.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core import config


class DuplicatePatternError(ValueError):
    """A pattern with this pattern_id is already registered."""


class PatternRegistry:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._by_id: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    envelope = json.loads(raw)
                    self._by_id[envelope["pattern"]["pattern_id"]] = envelope
        except FileNotFoundError:
            pass

    def add(self, pattern: dict[str, Any], *, source_node_id: str) -> dict[str, Any]:
        """Store a validated pattern; returns the stored envelope."""
        pid = pattern["pattern_id"]
        with self._lock:
            if pid in self._by_id:
                raise DuplicatePatternError(pid)
            envelope = {
                "pattern": pattern,
                "registered_by": source_node_id,
                "registered_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(envelope, ensure_ascii=True, sort_keys=True) + "\n")
            self._by_id[pid] = envelope
        return envelope

    def get(self, pattern_id: str) -> dict[str, Any] | None:
        return self._by_id.get(pattern_id)

    def list(self, *, typology: str | None = None) -> list[dict[str, Any]]:
        items = list(self._by_id.values())
        if typology:
            items = [e for e in items if e["pattern"].get("typology") == typology]
        return sorted(items, key=lambda e: e["registered_at"])

    def __len__(self) -> int:
        return len(self._by_id)


_instances: dict[str, PatternRegistry] = {}
_instances_lock = threading.Lock()


def get_registry() -> PatternRegistry:
    """Singleton per resolved path — tests point NASEEJ_REGISTRY_PATH at a
    temp file and automatically get a fresh, isolated registry."""
    path = config.registry_path()
    key = str(path)
    with _instances_lock:
        if key not in _instances:
            _instances[key] = PatternRegistry(path)
        return _instances[key]
