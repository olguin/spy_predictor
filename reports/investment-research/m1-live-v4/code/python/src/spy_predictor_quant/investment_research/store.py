"""Atomic checkpoints and immutable content-addressed research artifacts."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path

from spy_predictor_quant.market_archive import content_hash, utc_now


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def lock(self):
        with (self.root / ".lock").open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Another controller owns this run") from None
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def save(self, state: dict) -> None:
        data = json.dumps(state, indent=2, allow_nan=False) + "\n"
        temp = self.root / "state.tmp"
        with temp.open("w") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(self.root / "state.json")

    def load(self) -> dict:
        return json.loads((self.root / "state.json").read_text())

    def put(self, kind: str, value: dict) -> str:
        identity = content_hash(value)
        directory = self.root / kind
        directory.mkdir(exist_ok=True)
        path = directory / f"{identity}.json"
        if path.exists():
            self.get(kind, identity)
        else:
            with path.open("x") as handle:
                handle.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return identity

    def get(self, kind: str, identity: str) -> dict:
        if len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
            raise ValueError("Invalid artifact identity")
        value = json.loads((self.root / kind / f"{identity}.json").read_text())
        if content_hash(value) != identity:
            raise ValueError("Artifact integrity mismatch")
        return value

    def event(self, state: dict, kind: str, **fields) -> None:
        state["events"].append({"at": utc_now(), "kind": kind, **fields})
        self.save(state)
