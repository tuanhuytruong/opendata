from test_api import client, upload_csv


def test_global_date_scope_filters_chart_overview_and_chat() -> None:
    data = upload_csv(
        "sale_date,channel,net_sales\n"
        "2026-01-01,Online,100\n"
        "2026-01-02,Retail,40\n"
        "2026-01-03,Online,60\n"
    )
    run_id = data["run_id"]
    scope = {"column": "sale_date", "start": "2026-01-02", "end": "2026-01-03"}
    chart = client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "date_scope": scope})
    assert chart.status_code == 200, chart.text
    assert chart.json()["request"]["date_scope"] == scope
    assert chart.json()["rows"][0]["value"] == 60.0
    overview = client.get(f"/api/runs/{run_id}/executive-overview?language=en&date_column=sale_date&start=2026-01-02&end=2026-01-03")
    assert overview.status_code == 200, overview.text
    assert overview.json()["applied_date_scope"] == scope
    assert next(card for card in overview.json()["scorecards"] if card["metric"] == "net_sales")["value"] == 100.0
    chat = client.post(f"/api/runs/{run_id}/chat", json={"message": "sales by channel", "language": "en", "date_scope": scope})
    assert chat.status_code == 200, chat.text
    assert chat.json()["chart"]["request"]["date_scope"] == scope


def test_global_date_scope_rejects_unsafe_or_reversed_ranges() -> None:
    data = upload_csv("sale_date,channel,net_sales\n2026-01-01,Online,100\n")
    run_id = data["run_id"]
    base = {"dimension": "channel", "metric": "net_sales"}
    assert client.post(f"/api/runs/{run_id}/chart", json={**base, "date_scope": {"column": "channel", "start": "2026-01-01"}}).status_code == 422
    assert client.post(f"/api/runs/{run_id}/chart", json={**base, "date_scope": {"column": "sale_date", "start": "2026-01-02", "end": "2026-01-01"}}).status_code == 422
    assert client.get(f"/api/runs/{run_id}/executive-overview?start=2026-01-01").status_code == 422


def test_report_layout_is_validated_persisted_and_exported_structurally() -> None:
    data = upload_csv("sale_date,channel,net_sales\n2026-01-01,Online,100\n2026-01-02,Retail,40\n")
    run_id = data["run_id"]
    saved = client.put(f"/api/runs/{run_id}/custom-report", json={
        "layout_blueprint": {"template": "sales_performance_review"},
        "pinned_artifacts": [{"artifact_id": "trend", "chart": {"dimension": "sale_date", "metric": "net_sales", "chart_type": "line"}}],
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()["layout_blueprint"] == {"template": "sales_performance_review"}
    loaded = client.get(f"/api/runs/{run_id}/custom-report").json()
    assert loaded["layout_blueprint"] == {"template": "sales_performance_review"}
    exported = client.get(f"/api/runs/{run_id}/report")
    assert exported.status_code == 200, exported.text
    assert "report-layout--sales_performance_review" in exported.text
    assert "data-slot='hero-trend'" in exported.text
    assert '"trend":["trend"]' in exported.text
    bad = client.put(f"/api/runs/{run_id}/custom-report", json={"layout_blueprint": {"template": "invented"}})
    assert bad.status_code == 422
