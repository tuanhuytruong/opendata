"""Small durable local store for report-run artifacts and operational state.

The pilot is deliberately filesystem-backed: metadata and data stay on the service
host, are atomically written, and expire together. It is replaceable by a database
store without changing API callers.
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import fcntl
import duckdb

from fastapi import HTTPException

RUN_ID = re.compile(r"[a-f0-9]{32}")
DEFAULT_RETENTION_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class ArtifactNotFoundError(FileNotFoundError):
    """A run artifact has not been written yet."""


class ArtifactMalformedError(ValueError):
    """A durable run artifact exists but is not valid JSON."""


class RunStore:
    def __init__(self, root: Path, retention_hours: int = DEFAULT_RETENTION_HOURS) -> None:
        if not 1 <= retention_hours <= 24 * 30:
            raise ValueError("retention_hours must be between 1 and 720.")
        self.root = root
        self.retention_hours = retention_hours

    def _dir(self, run_id: str) -> Path:
        if not RUN_ID.fullmatch(run_id):
            raise HTTPException(404, "Report run was not found.")
        return self.root / run_id

    def _metadata_path(self, run_id: str) -> Path:
        return self._dir(run_id) / "run.json"

    def save_dataset(self, run_id: str, headers: list[str], rows: list[dict[str, str]], *, file_name: str, source_type: str = "file", source_label: str | None = None) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        directory = self._dir(run_id)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        data_path = directory / "dataset.csv"
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=directory, delete=False) as output:
            writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            output.flush()
            os.fsync(output.fileno())
            temporary = output.name
        os.chmod(temporary, 0o600)
        os.replace(temporary, data_path)
        created = _now()
        record = {
            "run_id": run_id,
            "file_name": file_name[:160],
            "source_type": source_type,
            "source_label": (source_label or file_name)[:180],
            "created_at": created.isoformat(),
            "expires_at": (created + timedelta(hours=self.retention_hours)).isoformat(),
            "status": "ready",
            "row_count": len(rows),
            "column_count": len(headers),
        }
        _atomic_write(directory / "run.json", json.dumps(record, separators=(",", ":")))

    def metadata(self, run_id: str) -> dict[str, Any]:
        path = self._metadata_path(run_id)
        if not path.exists():
            raise HTTPException(404, "Report run was not found or has expired.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            expires_at = datetime.fromisoformat(str(data["expires_at"]))
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise HTTPException(404, "Report run metadata is unavailable.") from error
        if expires_at <= _now():
            shutil.rmtree(self._dir(run_id), ignore_errors=True)
            raise HTTPException(404, "Report run has expired.")
        return data

    def load_dataset(self, run_id: str) -> tuple[list[str], list[dict[str, str]]]:
        self.metadata(run_id)
        path = self._dir(run_id) / "dataset.csv"
        if not path.exists():
            raise HTTPException(404, "Report run data is unavailable.")
        with path.open(encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            return list(reader.fieldnames or []), list(reader)

    def dataset_path(self, run_id: str) -> Path:
        self.metadata(run_id)
        return self._dir(run_id) / "dataset.csv"

    def analytics_database_path(self, run_id: str) -> Path:
        """A run-local DuckDB relation survives requests but expires with the run."""
        self.metadata(run_id)
        return self._dir(run_id) / "analytics.duckdb"

    @contextmanager
    def analytics_connection(self, run_id: str) -> Iterator[duckdb.DuckDBPyConnection]:
        """Open the authorized run relation, creating it once under a filesystem lock."""
        self.metadata(run_id)
        database_path = self.analytics_database_path(run_id)
        with self.locked_artifact(run_id, "analytics"):
            connection = duckdb.connect(str(database_path))
            try:
                exists = connection.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema = 'main' AND table_name = 'dataset'"
                ).fetchone()
                if not exists:
                    connection.execute(
                        "CREATE TABLE dataset AS SELECT * FROM read_csv_auto(?, all_varchar=true)",
                        [str(self.dataset_path(run_id))],
                    )
            except Exception:
                connection.close()
                raise
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def locked_artifact(self, run_id: str, name: str) -> Iterator[None]:
        """Serialize read-modify-write transitions for one run artifact."""
        self.metadata(run_id)
        path = self._dir(run_id) / f".{name}.lock"
        with path.open("a+", encoding="utf-8") as lock:
            os.chmod(path, 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def save_artifact_json(self, run_id: str, name: str, value: dict[str, Any]) -> None:
        self.metadata(run_id)
        _atomic_write(self._dir(run_id) / name, json.dumps(value, indent=2, ensure_ascii=False))

    def save_export(self, run_id: str, export_id: str, html_text: str, manifest: dict[str, Any]) -> None:
        self.metadata(run_id)
        if not re.fullmatch(r"[a-f0-9-]{8,80}", export_id):
            raise HTTPException(422, "Export ID is invalid.")
        directory = self._dir(run_id) / "exports" / export_id
        _atomic_write(directory / "report.html", html_text)
        _atomic_write(directory / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    def export_text(self, run_id: str, export_id: str, name: str = "report.html") -> str:
        self.metadata(run_id)
        if not re.fullmatch(r"[a-f0-9-]{8,80}", export_id) or name not in {"report.html", "manifest.json"}:
            raise HTTPException(404, "Report export was not found.")
        path = self._dir(run_id) / "exports" / export_id / name
        if not path.exists():
            raise HTTPException(404, "Report export was not found.")
        try:
            return path.read_text(encoding="utf-8")
        except OSError as error:
            raise HTTPException(500, "Report export is unavailable.") from error

    def export_manifest(self, run_id: str, export_id: str) -> dict[str, Any]:
        try:
            return json.loads(self.export_text(run_id, export_id, "manifest.json"))
        except json.JSONDecodeError as error:
            raise HTTPException(500, "Report export manifest is invalid.") from error

    def artifact_json(self, run_id: str, name: str) -> dict[str, Any]:
        self.metadata(run_id)
        path = self._dir(run_id) / name
        if not path.exists():
            raise ArtifactNotFoundError(name)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ArtifactMalformedError(name) from error
        except OSError as error:
            raise HTTPException(500, "Report artifact is unavailable.") from error
        if not isinstance(value, dict):
            raise ArtifactMalformedError(name)
        return value

    def cleanup_expired(self) -> int:
        if not self.root.exists():
            return 0
        removed = 0
        for directory in self.root.iterdir():
            if not directory.is_dir() or not RUN_ID.fullmatch(directory.name):
                continue
            try:
                self.metadata(directory.name)
            except HTTPException:
                if directory.exists():
                    shutil.rmtree(directory, ignore_errors=True)
                removed += 1
        return removed


class DurableJobQueue:
    """Filesystem queue with retry/cancellation state suitable for the pilot worker."""
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, job_id: str) -> Path:
        if not RUN_ID.fullmatch(job_id):
            raise HTTPException(404, "Job was not found.")
        return self.root / f"{job_id}.json"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Serialize filesystem queue transitions across API and worker processes."""
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = self.root / ".queue.lock"
        with lock_path.open("a+", encoding="utf-8") as lock:
            os.chmod(lock_path, 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def create(self, job_id: str, run_id: str, kind: str, max_attempts: int = 3) -> dict[str, Any]:
        record = {"job_id": job_id, "run_id": run_id, "kind": kind, "status": "queued", "attempt": 0, "max_attempts": max_attempts, "created_at": _now().isoformat(), "updated_at": _now().isoformat(), "error": None}
        with self._locked():
            _atomic_write(self._path(job_id), json.dumps(record, separators=(",", ":")))
        return record

    def get(self, job_id: str) -> dict[str, Any]:
        path = self._path(job_id)
        if not path.exists():
            raise HTTPException(404, "Job was not found.")
        return json.loads(path.read_text(encoding="utf-8"))

    def update(self, job_id: str, **changes: Any) -> dict[str, Any]:
        with self._locked():
            record = self.get(job_id)
            if record["status"] in {"completed", "cancelled"}:
                return record
            record.update(changes, updated_at=_now().isoformat())
            _atomic_write(self._path(job_id), json.dumps(record, separators=(",", ":")))
            return record

    def cancel(self, job_id: str) -> dict[str, Any]:
        return self.update(job_id, status="cancelled")

    def claim_next(self) -> dict[str, Any] | None:
        """Atomically select and transition one queued job to running."""
        with self._locked():
            for path in sorted(self.root.glob("*.json")):
                record = json.loads(path.read_text(encoding="utf-8"))
                if record.get("status") != "queued":
                    continue
                record.update(status="running", updated_at=_now().isoformat())
                _atomic_write(path, json.dumps(record, separators=(",", ":")))
                return record
        return None

    def next_queued(self) -> dict[str, Any] | None:
        """Read-only compatibility helper. Workers must call claim_next()."""
        if not self.root.exists():
            return None
        for path in sorted(self.root.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") == "queued":
                return record
        return None

    def fail_or_retry(self, job_id: str, reason: str) -> dict[str, Any]:
        record = self.get(job_id)
        if record["status"] == "cancelled":
            return record
        attempt = int(record["attempt"]) + 1
        return self.update(job_id, attempt=attempt, status="queued" if attempt < int(record["max_attempts"]) else "failed", error=reason[:240])


def redacted_error(error: Exception) -> str:
    """Stable external error category; never return driver/connection details."""
    if isinstance(error, HTTPException):
        return str(error.detail) if error.status_code < 500 else "The requested operation is temporarily unavailable."
    return "The requested operation could not be completed."
