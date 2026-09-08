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


def test_global_date_scope_rejects_unsafe_reversed_and_out_of_profile_ranges() -> None:
    data = upload_csv("sale_date,channel,net_sales\n2026-01-01,Online,100\n")
    run_id = data["run_id"]
    base = {"dimension": "channel", "metric": "net_sales"}
    assert client.post(f"/api/runs/{run_id}/chart", json={**base, "date_scope": {"column": "channel", "start": "2026-01-01"}}).status_code == 422
    assert client.post(f"/api/runs/{run_id}/chart", json={**base, "date_scope": {"column": "sale_date", "start": "2026-01-02", "end": "2026-01-01"}}).status_code == 422
    assert client.post(f"/api/runs/{run_id}/chart", json={**base, "date_scope": {"column": "sale_date", "start": "2025-12-31"}}).status_code == 422
    assert client.post(f"/api/runs/{run_id}/chart", json={**base, "date_scope": {"column": "sale_date", "end": "2026-01-02"}}).status_code == 422
    assert client.get(f"/api/runs/{run_id}/executive-overview?start=2026-01-01").status_code == 422


def test_profile_exposes_each_time_field_full_bounds_and_scorecards_compare_only_explicit_scope() -> None:
    data = upload_csv(
        "sale_date,delivery_date,net_sales\n"
        "2026-01-01,2026-02-01,10\n2026-01-02,2026-02-03,20\n"
        "2026-01-03,2026-02-05,30\n2026-01-04,2026-02-07,40\n"
    )
    run_id = data["run_id"]
    bounds = {item["column"]: item for item in data["time_field_bounds"]}
    assert bounds["sale_date"] == {"column": "sale_date", "min_date": "2026-01-01", "max_date": "2026-01-04"}
    assert bounds["delivery_date"] == {"column": "delivery_date", "min_date": "2026-02-01", "max_date": "2026-02-07"}

    full = next(item for item in client.get(f"/api/runs/{run_id}/executive-overview?language=en").json()["scorecards"] if item["metric"] == "net_sales")
    assert full["prior_period_value"] is None
    assert full["change_pct"] is None
    assert full["sparkline"] is None

    scoped = next(item for item in client.get(
        f"/api/runs/{run_id}/executive-overview?language=en&date_column=sale_date&start=2026-01-03&end=2026-01-04"
    ).json()["scorecards"] if item["metric"] == "net_sales")
    assert scoped["value"] == 70
    assert scoped["prior_period_value"] == 30
    assert scoped["change_pct"] == round((70 - 30) / 30 * 100, 2)
    assert scoped["current_period_label"] == "2026-01-03 to 2026-01-04"
    assert scoped["prior_period_label"] == "2026-01-01 to 2026-01-02"

    unavailable_prior = next(item for item in client.get(
        f"/api/runs/{run_id}/executive-overview?language=en&date_column=sale_date&start=2026-01-01&end=2026-01-02"
    ).json()["scorecards"] if item["metric"] == "net_sales")
    assert unavailable_prior["prior_period_value"] is None
    assert unavailable_prior["sparkline"] is None


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
    # Exported layout slots carry the same validated visual payload as the editor,
    # rather than only detached title placeholders.
    hero = exported.text.split("data-slot='hero-trend'", 1)[1].split("</section>", 1)[0]
    assert "report-chart" in hero
    assert "slot-artifact" in hero
    for template in ("executive_briefing", "category_division_deep_dive", "weekly_monthly_business_review"):
        response = client.put(f"/api/runs/{run_id}/custom-report", json={
            "layout_blueprint": {"template": template},
            "pinned_artifacts": [{"artifact_id": "trend", "chart": {"dimension": "sale_date", "metric": "net_sales", "chart_type": "line"}}],
        })
        assert response.status_code == 200, response.text
        exported = client.get(f"/api/runs/{run_id}/report")
        assert f"report-layout--{template}" in exported.text
        assert "report-chart" in exported.text
    bad = client.put(f"/api/runs/{run_id}/custom-report", json={"layout_blueprint": {"template": "invented"}})
    assert bad.status_code == 422
