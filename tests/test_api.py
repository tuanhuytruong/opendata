from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from main import app  # noqa: E402

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_profiles_csv_and_emits_quantity_warning() -> None:
    content = (
        "sale_date,net_sales,quantity,unit_of_measure,channel\n"
        "2026-08-01,100.5,2,EA,Online\n"
        "2026-08-02,130.5,3,KG,Retail\n"
    )
    response = client.post(
        "/api/runs/upload",
        files={"file": ("sales.csv", content, "text/csv")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["row_count"] == 2
    assert data["column_count"] == 5
    assert {item["name"]: item["kind"] for item in data["columns"]}["net_sales"] == "num"
    assert {item["name"]: item["kind"] for item in data["columns"]}["sale_date"] == "time"
    assert any("multiple units" in warning for warning in data["warnings"])


def test_rejects_non_csv() -> None:
    response = client.post(
        "/api/runs/upload",
        files={"file": ("sales.xlsx", b"not-a-workbook", "application/octet-stream")},
    )
    assert response.status_code == 415
