"""Append-only local storage primitives for market-data captures."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_immutable_run_directory(root: Path, kind: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = root / f"{kind}-{timestamp}-{uuid.uuid4().hex[:8]}"
    path.mkdir()
    return path


class NdjsonWriter:
    """Write and hash NDJSON records without permitting replacement."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._output = path.open("x", encoding="utf-8")
        self._hasher = hashlib.sha256()
        self._lock = threading.Lock()
        self.count = 0
        self._closed = False

    def write(self, record: dict[str, object]) -> None:
        encoded = canonical_json_bytes(record) + b"\n"
        with self._lock:
            if self._closed:
                raise RuntimeError(f"Writer for {self.path} is closed")
            self._output.write(encoded.decode("utf-8"))
            self._output.flush()
            self._hasher.update(encoded)
            self.count += 1

    @property
    def sha256(self) -> str:
        return self._hasher.hexdigest()

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._output.close()
                self._closed = True


class LiveSessionArchiveWriter:
    """Rotate real-time raw callbacks by instrument and trading session."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._control = NdjsonWriter(directory / "raw-control.ndjson")
        self._sessions: dict[tuple[str, str], NdjsonWriter] = {}
        self._lock = threading.Lock()
        self._closed = False

    def write(self, record: dict[str, object]) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError(f"Live archive writer for {self.directory} is closed")
            if record.get("type") == "realtimeBar":
                instrument = str(record["instrument"])
                raw_bar = record.get("bar")
                if not isinstance(raw_bar, dict):
                    raise ValueError("Real-time callback is missing its bar payload")
                session_date = _trading_session_date(
                    instrument,
                    int(raw_bar["time"]),
                )
                key = (instrument, session_date)
                writer = self._sessions.get(key)
                if writer is None:
                    writer = NdjsonWriter(
                        self.directory
                        / f"raw-{instrument}-session-{session_date}.ndjson"
                    )
                    self._sessions[key] = writer
                writer.write(record)
            else:
                self._control.write(record)

    @property
    def count(self) -> int:
        return self._control.count + sum(
            writer.count for writer in self._sessions.values()
        )

    @property
    def sha256(self) -> str:
        identity = [
            {
                "file": Path(entry["path"]).name,
                "records": entry["records"],
                "sha256": entry["sha256"],
            }
            for entry in self.file_manifest()
        ]
        return content_hash(identity)

    def file_manifest(self) -> list[dict[str, object]]:
        entries = [
            {
                "kind": "control",
                "path": str(self._control.path),
                "records": self._control.count,
                "sha256": self._control.sha256,
            }
        ]
        entries.extend(
            {
                "kind": "session",
                "instrument": instrument,
                "sessionDate": session_date,
                "path": str(writer.path),
                "records": writer.count,
                "sha256": writer.sha256,
            }
            for (instrument, session_date), writer in sorted(self._sessions.items())
        )
        return entries

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._control.close()
            for writer in self._sessions.values():
                writer.close()
            self._closed = True


def _trading_session_date(instrument: str, epoch: int) -> str:
    if instrument in {"SPY", "QQQ"}:
        local = datetime.fromtimestamp(epoch, timezone.utc).astimezone(
            ZoneInfo("America/New_York")
        )
        return local.date().isoformat()
    if instrument in {"ES", "NQ"}:
        local = datetime.fromtimestamp(epoch, timezone.utc).astimezone(
            ZoneInfo("America/Chicago")
        )
        session_date = local.date()
        if local.hour >= 17:
            session_date += timedelta(days=1)
        return session_date.isoformat()
    raise ValueError(f"Unsupported live-capture instrument {instrument}")


def write_ndjson_exclusive(
    path: Path,
    records: Iterable[dict[str, object]],
) -> tuple[int, str]:
    writer = NdjsonWriter(path)
    try:
        for record in records:
            writer.write(record)
        return writer.count, writer.sha256
    finally:
        writer.close()


def write_json_exclusive(path: Path, value: object) -> str:
    encoded = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with path.open("x", encoding="utf-8") as output:
        output.write(encoded)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def write_bytes_exclusive(path: Path, value: bytes) -> str:
    with path.open("xb") as output:
        output.write(value)
    return hashlib.sha256(value).hexdigest()


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected object at {path}:{line_number}")
            records.append(value)
    return records
