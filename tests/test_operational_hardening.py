from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from main import app  # noqa: E402
from run_store import DurableJobQueue, RunStore  # noqa: E402

client = TestClient(app)


def upload_csv(content: str) -> dict:
    response = client.post("/api/runs/upload", files={"file": ("safe.csv", content, "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()


def test_run_store_isolated_artifacts_expiry_and_cleanup(tmp_path) -> None:
    store = RunStore(tmp_path, retention_hours=1)
    run_id = "a" * 32
    store.save_dataset(run_id, ["channel", "net_sales"], [{"channel": "Online", "net_sales": "100"}], file_name="sales.csv")
    assert (tmp_path / run_id / "dataset.csv").exists()
    assert (tmp_path / run_id).stat().st_mode & 0o777 == 0o700
    assert (tmp_path / run_id / "dataset.csv").stat().st_mode & 0o777 == 0o600
    assert store.metadata(run_id)["source_type"] == "file"
    record = store.metadata(run_id)
    record["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    (tmp_path / run_id / "run.json").write_text(__import__("json").dumps(record))
    assert store.cleanup_expired() == 1
    assert not (tmp_path / run_id).exists()


def test_durable_job_retries_and_cancellation(tmp_path) -> None:
    queue = DurableJobQueue(tmp_path)
    job_id = "b" * 32
    queue.create(job_id, "a" * 32, "profile", max_attempts=2)
    assert queue.next_queued()["job_id"] == job_id
    assert queue.fail_or_retry(job_id, "private host details") ["status"] == "queued"
    assert queue.fail_or_retry(job_id, "private host details")["status"] == "failed"
    second = "c" * 32
    queue.create(second, "a" * 32, "report")
    assert queue.cancel(second)["status"] == "cancelled"
    assert queue.cancel(second)["status"] == "cancelled"


def test_api_security_headers_and_sensitive_masking() -> None:
    data = upload_csv("email,channel,net_sales\nalice@example.com,Online,100\n")
    assert data["preview"][0]["email"] == "[masked]"
    assert client.get("/api/health").headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/health").headers["x-frame-options"] == "DENY"
    run_id = data["run_id"]
    assert client.get(f"/api/runs/{run_id}/values/email").status_code == 422
    assert client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "filters": [{"column": "email", "value": "alice@example.com"}]}).status_code == 422
    assert client.post(f"/api/runs/{run_id}/parse-filter", json={"text": "email = alice@example.com"}).status_code == 422


def test_readiness_deletion_and_job_api() -> None:
    data = upload_csv("channel,net_sales\nOnline,100\n")
    assert client.get("/api/readiness").status_code == 200
    queued = client.post("/api/jobs", json={"run_id": data["run_id"], "kind": "report"})
    assert queued.status_code == 202, queued.text
    job_id = queued.json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "queued"
    assert client.delete(f"/api/jobs/{job_id}").json()["status"] == "cancelled"
    assert client.delete(f"/api/runs/{data['run_id']}").status_code == 204
    assert client.get(f"/api/runs/{data['run_id']}/plan").status_code == 404


def test_maintenance_cleanup_is_disabled_without_secret() -> None:
    assert client.post("/api/maintenance/cleanup").status_code == 404


def test_report_payload_cannot_close_script_tag() -> None:
    data = upload_csv("channel,net_sales\n</script><img src=x onerror=alert(1)>,100\n")
    response = client.post(f"/api/runs/{data['run_id']}/report", json={"charts": [{"dimension": "channel", "metric": "net_sales"}]})
    assert response.status_code == 200
    assert "<\\/script><img" in response.text
    assert "</script><img" not in response.text


def test_csv_row_limit_is_enforced(monkeypatch) -> None:
    import main
    monkeypatch.setattr(main, "MAX_PROFILE_ROWS", 1)
    response = client.post("/api/runs/upload", files={"file": ("large.csv", "channel,net_sales\nOnline,1\nRetail,2\n", "text/csv")})
    assert response.status_code == 422
    assert "exceeds" in response.json()["detail"]
