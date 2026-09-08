"""Intent preservation and grounded evidence regressions (real DuckDB aggregates)."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
import main
from planning import evidence_for_chart

client = TestClient(main.app)

@pytest.fixture
def run(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    text = "store,region,channel,net_sales,profit,sale_date\nA,East,Online,10,2,2026-01-01\nB,East,Retail,30,3,2026-01-02\nC,West,Online,100,4,2026-01-03\nD,West,Retail,200,5,2026-01-04\n"
    response = client.post("/api/runs/upload", files={"file": ("intent.csv", text, "text/csv")})
    assert response.status_code == 201
    return response.json()["run_id"]

def chat(run, message):
    response = client.post(f"/api/runs/{run}/chat", json={"message": message, "language": "en"})
    assert response.status_code == 200, response.text
    return response.json()

def test_explicit_filter_and_table_are_preserved(run):
    result = chat(run, "Show a table of net_sales by store where channel = Online")
    assert result["chart"] is None
    assert {row["label"] for row in result["table"]} == {"A", "C"}
    assert "Online" in result["scope"]

def test_average_and_top_limit_are_preserved(run):
    result = chat(run, "Show top 1 channel by average net_sales")
    assert result["chart"]["aggregation"] == "avg"
    assert result["chart"]["result_count"] == 1
    assert result["chart"]["request"] == {
        "dimension": "channel", "metric": "net_sales", "aggregation": "avg",
        "chart_type": "bar", "x_metric": None, "secondary_metric": None, "secondary_dimension": None,
        "limit_per_secondary": False, "limit": 1, "filters": [],
    }

@pytest.mark.parametrize("message", [
    "Show net_sales and profit by store",
    "Show top 2 departments by sales per division",
    "Show sales by store where unknown = Online",
    "Show sales by store for last month",
    "Show sales by store as scatter",
])
def test_incomplete_explicit_intent_never_runs_partial_aggregate(run, message):
    result = chat(run, message)
    assert result["mode"] == "clarification"
    assert result["table"] == []

def test_requested_donut_is_preserved(run):
    assert chat(run, "Show net_sales by channel as donut")["chart"]["chart_type"] == "donut"

def test_partition_evidence_finds_actual_leader(run):
    result = chat(run, "top 1 stores sales by region")
    assert "D" in result["insight"]
    assert "200" in result["insight"]
    assert "region" in result["scope"]

def test_exact_intent_not_overridden_by_llm_clarification(run, monkeypatch):
    monkeypatch.setattr(main, "_llm_chart_request", lambda *args: (None, "Which metric?"))
    assert chat(run, "top 1 stores sales by region")["mode"] == "analysis"

def test_new_starter_question_invalidates_pending_choice(run):
    pending = chat(run, "Help analyze")
    option = pending["clarification_options"][0]
    chat(run, "Suggest analyses")
    response = client.post(f"/api/runs/{run}/semantic-selection", json={"column": option["column"], "role": option["role"], "language": "en"})
    assert "submit the question again" in response.json()["answer"]

def test_report_evidence_not_first_chronological_row():
    evidence = evidence_for_chart(SimpleNamespace(title="Trend", rows=[{"label": "Jan", "value": 10}, {"label": "Feb", "value": 100}]))
    assert evidence[0]["label"] == "Feb"

def test_zero_baseline_does_not_claim_zero_percent_growth():
    headline, _ = main.chart_insight([{"display_label": "Jan", "value": 0}, {"display_label": "Feb", "value": 100}], True, "en")
    assert "0%" not in headline
    assert "undefined" in headline


def test_top_date_lookup_returns_direct_kpi_not_a_trend_chart(run):
    result = chat(run, "Which date has top sales?")
    assert result["mode"] == "analysis"
    assert result["output_mode"] == "kpi"
    assert result["chart"] is None
    assert len(result["table"]) == 1
    assert result["table"][0]["label"] == "2026-01-04"
    assert result["table"][0]["value"] == 200
    assert "04-Jan-26 has the highest Net Sales at 200." == result["answer"]


def test_top_n_title_reports_actual_available_count_and_requested_limit(run):
    response = client.post(
        f"/api/runs/{run}/chart?language=en",
        json={"dimension": "store", "metric": "net_sales", "chart_type": "bar", "limit": 12},
    )
    assert response.status_code == 200, response.text
    chart = response.json()
    assert chart["requested_limit"] == 12
    assert chart["result_count"] == 4
    assert chart["title"] == "Top 4 Store by Sales"
    assert any("Only 4 valid categories are available (requested Top 12)." == warning for warning in chart["warnings"])


def test_cost_display_label_preserves_business_capitalization(run):
    second = client.post(
        "/api/runs/upload",
        files={"file": ("cost.csv", "store,cost\nA,10\nB,5\n", "text/csv")},
    ).json()["run_id"]
    chart = client.post(f"/api/runs/{second}/chart?language=en", json={"dimension": "store", "metric": "cost", "limit": 12}).json()
    assert chart["metric_display_name"] == "Cost"
    assert chart["title"] == "Top 2 Store by Cost"
