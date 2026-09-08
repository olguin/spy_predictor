"""Resumable immutable HTTP-page capture for historical market data."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from spy_predictor_quant.market_archive import (
    file_sha256,
    utc_now,
    write_bytes_exclusive,
    write_json_exclusive,
)


@dataclass(frozen=True)
class ArchivedPage:
    provider: str
    page: int
    path: Path
    sha256: str
    received_at: str
    request_url: str
    records: int


@dataclass(frozen=True)
class ArchivedResource:
    provider: str
    path: Path
    sha256: str
    received_at: str
    request_url: str
    records: int
    content_type: str


class RequestLimiter:
    def __init__(self, maximum_requests_per_minute: int) -> None:
        if maximum_requests_per_minute <= 0:
            raise ValueError("maximum_requests_per_minute must be positive")
        self.minimum_spacing = 60.0 / maximum_requests_per_minute
        self.last_request_at: float | None = None

    def wait(self) -> None:
        if self.last_request_at is not None:
            remaining = self.minimum_spacing - (time.monotonic() - self.last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        self.last_request_at = time.monotonic()


def capture_pages(
    *,
    provider: str,
    initial_url: str,
    raw_directory: Path,
    headers: dict[str, str],
    limiter: RequestLimiter,
    next_url: Callable[[dict[str, Any], str], str | None],
    extract_records: Callable[[dict[str, Any]], list[dict[str, Any]]],
    maximum_retries: int = 5,
    allow_network: bool = True,
    secret_query: dict[str, str] | None = None,
    request_timeout_seconds: float = 60,
    record_extraction_version: str = "v1",
) -> tuple[list[ArchivedPage], list[dict[str, Any]]]:
    if not record_extraction_version:
        raise ValueError("record_extraction_version cannot be empty")
    raw_directory.mkdir(parents=True, exist_ok=True)
    pages: list[ArchivedPage] = []
    records: list[dict[str, Any]] = []
    request_url: str | None = _sanitized_url(initial_url)
    page_number = 0
    while request_url:
        raw_path = raw_directory / f"page-{page_number:04d}.json"
        metadata_path = raw_directory / f"page-{page_number:04d}.meta.json"
        if raw_path.exists():
            raw = raw_path.read_bytes()
            metadata = _load_or_recover_metadata(
                provider,
                request_url,
                raw_path,
                metadata_path,
                extract_records,
            )
        else:
            if not allow_network:
                raise FileNotFoundError(
                    f"Offline run is missing archived page {raw_path}"
                )
            raw, status, received_at = _request_with_retry(
                _with_secret_query(request_url, secret_query),
                headers,
                limiter,
                maximum_retries,
                timeout_seconds=request_timeout_seconds,
            )
            page_hash = write_bytes_exclusive(raw_path, raw)
            payload = json.loads(raw)
            page_records = extract_records(payload)
            metadata = {
                "schemaVersion": "archived-http-page-v1",
                "recordExtractionVersion": record_extraction_version,
                "provider": provider,
                "page": page_number,
                "requestUrl": _sanitized_url(request_url),
                "httpStatus": status,
                "receivedAt": received_at,
                "records": len(page_records),
                "sha256": page_hash,
            }
            write_json_exclusive(metadata_path, metadata)

        actual_hash = file_sha256(raw_path)
        if actual_hash != metadata.get("sha256"):
            raise ValueError(
                f"Archived page hash mismatch for {raw_path}: "
                f"expected {metadata.get('sha256')}, got {actual_hash}"
            )
        if _sanitized_url(request_url) != metadata.get("requestUrl"):
            raise ValueError(
                f"Archived page request mismatch for {raw_path}; refuse cache reuse"
            )
        payload = json.loads(raw)
        page_records = extract_records(payload)
        metadata_extraction_version = str(
            metadata.get("recordExtractionVersion", "v1")
        )
        if metadata_extraction_version == record_extraction_version:
            extraction_metadata = metadata
        else:
            extraction_metadata = _load_or_create_extraction_metadata(
                provider=provider,
                raw_path=raw_path,
                metadata_path=metadata_path,
                raw_sha256=actual_hash,
                record_extraction_version=record_extraction_version,
                records=len(page_records),
            )
        expected_records = int(extraction_metadata.get("records", -1))
        if len(page_records) != expected_records:
            raise ValueError(f"Archived page record count mismatch for {raw_path}")
        records.extend(page_records)
        pages.append(
            ArchivedPage(
                provider=provider,
                page=page_number,
                path=raw_path,
                sha256=actual_hash,
                received_at=str(metadata["receivedAt"]),
                request_url=str(metadata["requestUrl"]),
                records=len(page_records),
            )
        )
        request_url = next_url(payload, request_url)
        if request_url:
            request_url = _sanitized_url(request_url)
        page_number += 1
    return pages, records


def capture_resource(
    *,
    provider: str,
    request_url: str,
    raw_path: Path,
    headers: dict[str, str],
    limiter: RequestLimiter,
    content_type: str,
    count_records: Callable[[bytes], int],
    maximum_retries: int = 5,
    allow_network: bool = True,
    secret_query: dict[str, str] | None = None,
) -> tuple[ArchivedResource, bytes]:
    """Capture one arbitrary byte resource with immutable request metadata."""
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = raw_path.with_name(raw_path.name + ".meta.json")
    safe_url = _sanitized_url(request_url)
    if raw_path.exists():
        raw = raw_path.read_bytes()
        if not metadata_path.exists():
            raise ValueError(f"Immutable resource metadata is missing for {raw_path}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        if not allow_network:
            raise FileNotFoundError(f"Offline run is missing archived resource {raw_path}")
        raw, status, received_at = _request_with_retry(
            _with_secret_query(request_url, secret_query),
            headers,
            limiter,
            maximum_retries,
        )
        records = count_records(raw)
        digest = write_bytes_exclusive(raw_path, raw)
        metadata = {
            "schemaVersion": "archived-http-resource-v1",
            "provider": provider,
            "requestUrl": safe_url,
            "httpStatus": status,
            "receivedAt": received_at,
            "records": records,
            "contentType": content_type,
            "sha256": digest,
        }
        write_json_exclusive(metadata_path, metadata)
    actual_hash = file_sha256(raw_path)
    if metadata.get("schemaVersion") != "archived-http-resource-v1":
        raise ValueError(f"Invalid immutable resource metadata for {raw_path}")
    if metadata.get("requestUrl") != safe_url:
        raise ValueError(f"Archived resource request mismatch for {raw_path}")
    if metadata.get("sha256") != actual_hash:
        raise ValueError(f"Archived resource hash mismatch for {raw_path}")
    actual_records = count_records(raw)
    if metadata.get("records") != actual_records:
        raise ValueError(f"Archived resource record count mismatch for {raw_path}")
    if metadata.get("contentType") != content_type:
        raise ValueError(f"Archived resource content type mismatch for {raw_path}")
    return (
        ArchivedResource(
            provider=provider,
            path=raw_path,
            sha256=actual_hash,
            received_at=str(metadata["receivedAt"]),
            request_url=safe_url,
            records=actual_records,
            content_type=content_type,
        ),
        raw,
    )


def _request_with_retry(
    url: str,
    headers: dict[str, str],
    limiter: RequestLimiter,
    maximum_retries: int,
    timeout_seconds: float = 60,
) -> tuple[bytes, int, str]:
    if timeout_seconds <= 0:
        raise ValueError("HTTP request timeout must be positive")
    safe_url = _sanitized_url(url)
    for attempt in range(maximum_retries + 1):
        limiter.wait()
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
                status = response.status
            return raw, status, utc_now()
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:1000]
            if error.code == 429 and attempt < maximum_retries:
                retry_after = error.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else max(12.5, 2**attempt)
                time.sleep(delay)
                continue
            if 500 <= error.code < 600 and attempt < maximum_retries:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(
                f"{safe_url} failed with HTTP {error.code}: {detail}"
            ) from error
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt >= maximum_retries:
                raise RuntimeError(f"{safe_url} failed: {error}") from error
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def _load_or_recover_metadata(
    provider: str,
    request_url: str,
    raw_path: Path,
    metadata_path: Path,
    extract_records: Callable[[dict[str, Any]], list[dict[str, Any]]],
) -> dict[str, Any]:
    if metadata_path.exists():
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Invalid page metadata {metadata_path}")
        return value
    received_at = datetime.fromtimestamp(
        raw_path.stat().st_mtime, timezone.utc
    ).isoformat()
    payload = json.loads(raw_path.read_bytes())
    record_count = len(extract_records(payload))
    metadata = {
        "schemaVersion": "archived-http-page-v1",
        "provider": provider,
        "page": int(raw_path.stem.split("-")[-1]),
        "requestUrl": _sanitized_url(request_url),
        "httpStatus": 200,
        "receivedAt": received_at,
        "records": record_count,
        "sha256": file_sha256(raw_path),
    }
    write_json_exclusive(metadata_path, metadata)
    return metadata


def _load_or_create_extraction_metadata(
    *,
    provider: str,
    raw_path: Path,
    metadata_path: Path,
    raw_sha256: str,
    record_extraction_version: str,
    records: int,
) -> dict[str, Any]:
    """Version a changed envelope parser without rewriting capture metadata."""

    safe_version = "".join(
        character
        for character in record_extraction_version
        if character.isascii() and (character.isalnum() or character in "-_")
    )
    if safe_version != record_extraction_version:
        raise ValueError("record_extraction_version contains unsafe characters")
    sidecar_path = raw_path.with_name(
        f"{raw_path.stem}.extraction-{record_extraction_version}.meta.json"
    )
    expected = {
        "schemaVersion": "archived-http-page-extraction-v1",
        "provider": provider,
        "page": int(raw_path.stem.split("-")[-1]),
        "baseMetadata": metadata_path.name,
        "baseMetadataSha256": file_sha256(metadata_path),
        "rawSha256": raw_sha256,
        "recordExtractionVersion": record_extraction_version,
        "records": records,
    }
    if sidecar_path.exists():
        actual = json.loads(sidecar_path.read_text(encoding="utf-8"))
        if actual != expected:
            raise ValueError(
                f"Archived page extraction metadata mismatch for {raw_path}"
            )
        return actual
    write_json_exclusive(sidecar_path, expected)
    return expected


def _sanitized_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    safe_query = [
        (key, item)
        for key, item in query
        if key.lower().replace("_", "") != "apikey"
    ]
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(safe_query),
            parsed.fragment,
        )
    )


def _with_secret_query(value: str, secret_query: dict[str, str] | None) -> str:
    if not secret_query:
        return value
    parsed = urllib.parse.urlsplit(value)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.extend(secret_query.items())
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )
