from io import BytesIO
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from main import app  # noqa: E402

client = TestClient(app)


def upload_csv(content: str, name: str = "sales.csv") -> dict:
    response = client.post("/api/runs/upload", files={"file": (name, content, "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()


def test_health() -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_profiles_csv_and_emits_quantity_warning() -> None:
    data = upload_csv("sale_date,net_sales,quantity,unit_of_measure,channel\n2026-08-01,100.5,2,EA,Online\n2026-08-02,130.5,3,KG,Retail\n")
    assert data["row_count"] == 2
    assert {item["name"]: item["kind"] for item in data["columns"]}["net_sales"] == "num"
    assert any("multiple units" in warning for warning in data["warnings"])


def test_profiles_xlsx() -> None:
    book = Workbook(); sheet = book.active
    sheet.append(["sale_date", "net_sales", "channel"])
    sheet.append(["2026-08-01", 100, "Online"])
    content = BytesIO(); book.save(content)
    response = client.post("/api/runs/upload", files={"file": ("sales.xlsx", content.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert response.status_code == 201, response.text
    assert response.json()["file_name"] == "sales.xlsx"


def test_values_and_validated_chart() -> None:
    data = upload_csv("channel,net_sales\nOnline,100\nRetail,40\nOnline,20\n")
    run_id = data["run_id"]
    assert client.get(f"/api/runs/{run_id}/values/channel").json()["values"] == ["Online", "Retail"]
    chart = client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "aggregation": "sum"})
    assert chart.status_code == 200, chart.text
    assert chart.json()["rows"][0] == {"label": "Online", "value": 120.0}
    assert client.post(f"/api/runs/{run_id}/chart", json={"dimension": "missing", "metric": "net_sales"}).status_code == 422


def test_rejects_unsupported_file() -> None:
    response = client.post("/api/runs/upload", files={"file": ("sales.xls", b"bad", "application/octet-stream")})
    assert response.status_code == 415
