from io import BytesIO
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from main import MAX_PROFILE_ROWS, MAX_UPLOAD_BYTES, app  # noqa: E402

client = TestClient(app)


def upload_csv(content: str, name: str = "sales.csv") -> dict:
    response = client.post("/api/runs/upload", files={"file": (name, content, "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()


def test_health() -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_configured_upload_limits_match_product_contract() -> None:
    assert MAX_UPLOAD_BYTES == 100 * 1024 * 1024
    assert MAX_PROFILE_ROWS == 600_000


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
    filtered = client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "filters": [{"column": "channel", "operator": "equals", "value": "Retail"}]})
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["rows"] == [{"label": "Retail", "value": 40.0}]
    assert client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "filters": [{"column": "missing", "value": "bad"}]}).status_code == 422
    assert client.post(f"/api/runs/{run_id}/chart", json={"dimension": "missing", "metric": "net_sales"}).status_code == 422
    numeric = client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "filters": [{"column": "net_sales", "operator": "greater_than", "value": "50"}]})
    assert numeric.status_code == 200, numeric.text
    assert numeric.json()["rows"] == [{"label": "Online", "value": 100.0}]
    assert client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "filters": [{"column": "net_sales", "operator": "greater_than", "value": "not-a-number"}]}).status_code == 422


def test_parses_explicit_filters_and_proposes_charts() -> None:
    data = upload_csv("sale_date,channel,net_sales\n2026-01-01,Online,100\n2026-01-02,Retail,40\n")
    run_id = data["run_id"]
    parsed = client.post(f"/api/runs/{run_id}/parse-filter", json={"text": "net_sales >= 50"})
    assert parsed.status_code == 200, parsed.text
    assert parsed.json()["filter"] == {"column": "net_sales", "operator": "greater_or_equal", "value": "50"}
    assert client.post(f"/api/runs/{run_id}/parse-filter", json={"text": "missing = bad"}).status_code == 422
    plan = client.get(f"/api/runs/{run_id}/plan?limit=2")
    assert plan.status_code == 200, plan.text
    assert 1 <= len(plan.json()["charts"]) <= 2


def test_builds_pareto_and_two_dimension_chart_contracts() -> None:
    data = upload_csv("channel,city,net_sales\nOnline,HCM,100\nOnline,Hanoi,20\nRetail,HCM,40\n")
    run_id = data["run_id"]
    pareto = client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "chart_type": "pareto"})
    assert pareto.status_code == 200, pareto.text
    assert pareto.json()["rows"][0]["cumulative_pct"] > 0
    heatmap = client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "secondary_dimension": "city", "metric": "net_sales", "chart_type": "heatmap"})
    assert heatmap.status_code == 200, heatmap.text
    assert heatmap.json()["rows"][0]["secondary_label"] == "HCM"
    assert client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "chart_type": "heatmap"}).status_code == 422


def test_builds_self_contained_report() -> None:
    data = upload_csv("channel,net_sales\nOnline,100\nRetail,40\n")
    response = client.post(f"/api/runs/{data['run_id']}/report", json={"title": "Sales report", "charts": [{"dimension": "channel", "metric": "net_sales"}]})
    assert response.status_code == 200, response.text
    assert "text/html" in response.headers["content-type"]
    assert "Sales report" in response.text
    assert "Online" in response.text
    assert "100.0" in response.text
    assert "Evidence-bound highlights" in response.text
    assert "Online is the leading segment" in response.text
    from main import DATA_DIR
    manifest = (DATA_DIR / f"{data['run_id']}.manifest.json").read_text()
    assert 'dataset_sha256' in manifest
    fetched_manifest = client.get(f"/api/runs/{data['run_id']}/manifest")
    assert fetched_manifest.status_code == 200
    assert fetched_manifest.json()["chart_count"] == 1


def test_rejects_unsupported_file() -> None:
    response = client.post("/api/runs/upload", files={"file": ("sales.xls", b"bad", "application/octet-stream")})
    assert response.status_code == 415
