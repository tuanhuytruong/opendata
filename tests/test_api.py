import json
from io import BytesIO
import json
from pathlib import Path
import sys
import time

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


def test_large_upload_returns_sampled_profile_then_lazily_completes_and_caches() -> None:
    headers = ["event_date", "amount", "channel", "region", "segment", "product", "quantity", "uom", "customer_id", "note"]
    row = "2026-01-01,100,Online,North,Consumer,Widget,2,EA,1,ok"
    content = ",".join(headers) + "\n" + (row + "\n") * 63_000

    started = time.perf_counter()
    response = client.post("/api/runs/upload", files={"file": ("large.csv", content, "text/csv")})
    attach_elapsed = time.perf_counter() - started
    assert response.status_code == 201, response.text
    attached = response.json()
    assert attached["row_count"] == 63_000
    assert attached["column_count"] == 10
    assert attached["profile_status"] == "sampled"
    assert attached["profiled_row_count"] == 1_000
    # Avoid a machine-specific latency threshold: prove upload avoided full profile
    # work by requiring the later full profile to inspect all retained rows.
    started = time.perf_counter()
    full_response = client.get(f"/api/runs/{attached['run_id']}/profile/status")
    full_elapsed = time.perf_counter() - started
    assert full_response.status_code == 200, full_response.text
    complete = full_response.json()
    assert complete["profile_status"] == "complete"
    assert complete["profiled_row_count"] == 63_000
    assert full_elapsed > 0
    assert attach_elapsed > 0

    cached_started = time.perf_counter()
    cached_response = client.get(f"/api/runs/{attached['run_id']}/profile/status")
    cached_elapsed = time.perf_counter() - cached_started
    assert cached_response.status_code == 200, cached_response.text
    assert cached_response.json() == complete
    assert cached_elapsed <= full_elapsed


def test_run_scoped_eda_is_deterministic_bounded_and_excludes_sensitive_values() -> None:
    data = upload_csv(
        "event_date,amount,channel,email\n"
        "2026-01-03,10,Online,alice@example.test\n"
        "2026-01-01,20,Retail,bob@example.test\n"
        "invalid-date,30,Online,carol@example.test\n"
        ",40,,dana@example.test\n"
    )
    url = f"/api/runs/{data['run_id']}/eda"
    first = client.get(url)
    second = client.get(url)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()
    body = first.json()
    assert body["run_id"] == data["run_id"]
    assert body["coverage"] == {
        "row_count": 4,
        "column_count": 4,
        "analyzed_column_count": 3,
        "suppressed_sensitive_column_count": 1,
        "suppressed_column_count": 0,
    }
    columns = {column["name"]: column for column in body["columns"]}
    assert "email" not in columns
    assert "alice@example.test" not in str(body)
    assert columns["amount"]["numeric_summary"] == {
        "valid_count": 4,
        "invalid_count": 0,
        "min": 10.0,
        "max": 40.0,
        "mean": 25.0,
        "median": 25.0,
    }
    assert columns["event_date"]["quality"]["null_count"] == 1
    assert columns["event_date"]["time_coverage"] == {
        "valid_count": 2,
        "invalid_count": 1,
        "start": "2026-01-01T00:00:00",
        "end": "2026-01-03T00:00:00",
    }
    assert columns["channel"]["top_categories"] == [
        {"value": "Online", "count": 2},
        {"value": "Retail", "count": 1},
    ]
    assert len(body["provenance"]["dataset_sha256"]) == 64
    assert body["provenance"]["analysis"] == "deterministic, bounded run-scoped summary"


def test_values_and_validated_chart() -> None:
    data = upload_csv("channel,net_sales\nOnline,100\nRetail,40\nOnline,20\n")
    run_id = data["run_id"]
    assert client.get(f"/api/runs/{run_id}/values/channel").json()["values"] == ["Online", "Retail"]
    chart = client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "aggregation": "sum"})
    assert chart.status_code == 200, chart.text
    assert chart.json()["rows"][0]["label"] == "Online"
    assert chart.json()["rows"][0]["value"] == 120.0
    assert chart.json()["rows"][0]["formatted_value"] == "120.0"
    filtered = client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "filters": [{"column": "channel", "operator": "equals", "value": "Retail"}]})
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["rows"][0]["label"] == "Retail"
    assert filtered.json()["rows"][0]["value"] == 40.0
    assert client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "filters": [{"column": "missing", "value": "bad"}]}).status_code == 422
    assert client.post(f"/api/runs/{run_id}/chart", json={"dimension": "missing", "metric": "net_sales"}).status_code == 422
    numeric = client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "filters": [{"column": "net_sales", "operator": "greater_than", "value": "50"}]})
    assert numeric.status_code == 200, numeric.text
    assert numeric.json()["rows"][0]["label"] == "Online"
    assert numeric.json()["rows"][0]["value"] == 100.0
    assert client.post(f"/api/runs/{run_id}/chart", json={"dimension": "channel", "metric": "net_sales", "filters": [{"column": "net_sales", "operator": "greater_than", "value": "not-a-number"}]}).status_code == 422


def test_parses_explicit_filters_and_proposes_charts() -> None:
    data = upload_csv("sale_date,channel,net_sales\n2026-01-01,Online,100\n2026-01-02,Retail,40\n")
    run_id = data["run_id"]
    analyst = client.get(f"/api/runs/{run_id}/analyst-proposals")
    assert analyst.status_code == 200, analyst.text
    proposal = analyst.json()["proposals"][0]
    assert proposal["request"]["dimension"] in {"sale_date", "channel"}
    assert proposal["request"]["metric"] == "net_sales"
    assert "raw rows" not in str(analyst.json()).lower()
    chat = client.post(f"/api/runs/{run_id}/chat", json={"message": "Doanh thu theo tháng thế nào?"})
    assert chat.status_code == 200, chat.text
    assert chat.json()["chart"]["metric"] == "net_sales"
    assert chat.json()["chart"]["chart_type"] == "line"
    assert "final period" in chat.json()["insight"].lower()
    assert chat.json()["chart"]["sort_mode"] == "chronological"
    parsed = client.post(f"/api/runs/{run_id}/parse-filter", json={"text": "net_sales >= 50"})
    assert parsed.status_code == 200, parsed.text
    assert parsed.json()["filter"] == {"column": "net_sales", "operator": "greater_or_equal", "value": "50"}
    assert client.post(f"/api/runs/{run_id}/parse-filter", json={"text": "missing = bad"}).status_code == 422
    plan = client.get(f"/api/runs/{run_id}/plan?limit=2")
    assert plan.status_code == 200, plan.text
    assert 1 <= len(plan.json()["charts"]) <= 2


def test_chat_starter_analysis_requests_return_deterministic_safe_cards() -> None:
    data = upload_csv(
        "sale_date,channel,region,segment,product_type,customer_id,net_sales\n"
        "2026-01-01,Online,North,Consumer,Hardware,1,100\n"
        "2026-01-02,Retail,South,Business,Software,2,40\n"
        "2026-01-03,Online,North,Consumer,Hardware,3,80\n"
    )
    run_id = data["run_id"]
    responses = [
        client.post(f"/api/runs/{run_id}/chat", json={"message": message})
        for message in ("Cho tôi 5 góc nhìn", "Gợi ý phân tích dữ liệu", "Please suggest analyses for this data", "Đánh giá dữ liệu")
    ]
    for response in responses:
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["mode"] == "analysis"
        assert body["planner"] == "deterministic"
        assert body["chart"] is None
        assert body["table"] == []
        assert 1 <= len(body["proposals"]) <= 5
        assert all(card["confidence"] == "profile-based" for card in body["proposals"])
        assert all(card["request"]["dimension"] != "customer_id" for card in body["proposals"])
        assert all(card["request"]["metric"] not in {"customer_id", "email"} for card in body["proposals"])
    assert responses[0].json()["proposals"] == responses[1].json()["proposals"]
    assert responses[0].json()["proposals"] == responses[2].json()["proposals"]
    assert "Here are safe starter" in responses[2].json()["answer"]


def test_starter_cards_rotate_across_eligible_metrics() -> None:
    data = upload_csv(
        "sale_date,channel,net_sales,cogs,gross_profit\n"
        "2026-01-01,Online,100,60,40\n"
        "2026-01-02,Retail,40,25,15\n"
    )
    proposals = client.get(f"/api/runs/{data['run_id']}/starter-views?language=en").json()["proposals"]
    assert [item["request"]["metric"] for item in proposals[:3]] == ["net_sales", "cogs", "gross_profit"]
    assert all(item["request"]["dimension"] == "sale_date" for item in proposals[:3])


def test_stream_chat_top_three_stores_sales_by_region_is_per_region_ranking() -> None:
    data = upload_csv(
        "sale_date,STORE,REGION,NET_SALES\n"
        "2026-01-01,A,North,100\n2026-01-02,B,North,90\n2026-01-03,C,North,80\n2026-01-04,D,North,70\n"
        "2026-01-01,A,South,10\n2026-01-02,B,South,50\n2026-01-03,C,South,40\n2026-01-04,D,South,30\n"
    )
    response = client.post(f"/api/runs/{data['run_id']}/chat/stream", json={"message": "top 3 stores sales by region", "language": "en"})
    assert response.status_code == 200, response.text
    assert "event: completed" in response.text
    payload = response.text.split("event: completed\ndata: ", 1)[1].split("\n\n", 1)[0]
    body = json.loads(payload)["response"]
    assert body["planner"] == "deterministic"
    assert body["title"] == "Top 3 Net Sales by Store per Region"
    chart = body["chart"]
    assert chart["metric"] == "NET_SALES"
    assert chart["dimension"] == "STORE"
    assert chart["secondary_dimension"] == "REGION"
    assert chart["chart_type"] == "bar"
    assert chart["sort_mode"] == "ranking"
    assert [(row["secondary_label"], row["label"]) for row in chart["rows"]] == [
        ("North", "A"), ("North", "B"), ("North", "C"),
        ("South", "B"), ("South", "C"), ("South", "D"),
    ]


def test_starter_views_stream_progress_and_semantic_clarification() -> None:
    data = upload_csv("sale_date,channel,net_sales,cogs\n2026-01-01,Online,100,70\n2026-01-02,Retail,40,30\n")
    run_id = data["run_id"]
    views = client.get(f"/api/runs/{run_id}/starter-views")
    assert views.status_code == 200, views.text
    assert 1 <= len(views.json()["proposals"]) <= 5
    assert all("question" in item for item in views.json()["proposals"])
    clarification = client.post(f"/api/runs/{run_id}/chat", json={"message": "Phân tích giúp anh"})
    assert clarification.status_code == 200, clarification.text
    assert clarification.json()["mode"] == "clarification"
    assert clarification.json()["clarification_options"]
    stream = client.post(f"/api/runs/{run_id}/chat/stream", json={"message": "Doanh thu theo ngày"})
    assert stream.status_code == 200, stream.text
    assert "event: planning" in stream.text
    assert "event: completed" in stream.text
    assert "event: aggregated" not in stream.text


def test_direct_schema_references_resolve_metric_and_dimension_without_clarification() -> None:
    data = upload_csv("region,gross_profit,net_sales\nNorth,30,100\nSouth,10,40\n")
    response = client.post(f"/api/runs/{data['run_id']}/chat", json={"message": "Show gross profit by region"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "analysis"
    assert body["chart"]["metric"] == "gross_profit"
    assert body["chart"]["dimension"] == "region"


def test_semantic_selection_is_run_scoped_user_provenance_and_resumes_pending_question() -> None:
    first = upload_csv("sale_date,net_sales,cogs\n2026-01-01,100,70\n2026-01-02,40,30\n")
    second = upload_csv("sale_date,net_sales,cogs\n2026-01-01,20,10\n")
    pending = client.post(f"/api/runs/{first['run_id']}/chat", json={"message": "Please analyze this"})
    assert pending.status_code == 200, pending.text
    option = pending.json()["clarification_options"][0]
    assert option["role"] == "metric"
    resumed = client.post(
        f"/api/runs/{first['run_id']}/semantic-selection",
        json={"column": option["column"], "role": option["role"]},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["mode"] == "analysis"
    from main import RUN_STORE
    state = RUN_STORE.artifact_json(first["run_id"], "semantic-selection.json")
    assert state["selections"] == [{"column": option["column"], "role": "metric", "provenance": "User"}]
    assert not (RUN_STORE._dir(second["run_id"]) / "semantic-selection.json").exists()
    assert client.post(f"/api/runs/{second['run_id']}/semantic-selection", json={"column": "net_sales", "role": "metric"}).status_code == 409
    assert client.post(f"/api/runs/{first['run_id']}/semantic-selection", json={"column": "missing", "role": "metric"}).status_code == 422


def test_time_charts_are_chronological_and_format_dates() -> None:
    data = upload_csv("sale_date,net_sales\n2026-07-12,100\n2026-07-01,40\n2026-07-03,80\n")
    run_id = data["run_id"]
    chart = client.post(f"/api/runs/{run_id}/chart", json={"dimension": "sale_date", "metric": "net_sales", "chart_type": "line", "limit": 12})
    assert chart.status_code == 200, chart.text
    body = chart.json()
    assert body["sort_mode"] == "chronological"
    assert [row["label"] for row in body["rows"]] == ["2026-07-01", "2026-07-03", "2026-07-12"]
    assert body["rows"][0]["display_label"] == "01-Jul-26"
    assert "cuối kỳ" in body["insight_headline"]


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
    from main import RUN_STORE
    manifest = (RUN_STORE._dir(data["run_id"]) / "report.manifest.json").read_text()
    assert 'dataset_sha256' in manifest
    fetched_manifest = client.get(f"/api/runs/{data['run_id']}/manifest")
    assert fetched_manifest.status_code == 200
    assert fetched_manifest.json()["chart_count"] == 1


def test_rejects_unsupported_file() -> None:
    response = client.post("/api/runs/upload", files={"file": ("sales.xls", b"bad", "application/octet-stream")})
    assert response.status_code == 415



def test_starter_views_are_dynamic_and_localized() -> None:
    data = upload_csv("event_date,revenue,channel\n2026-01-01,100,Online\n2026-01-02,40,Retail\n")
    run_id = data["run_id"]
    english = client.get(f"/api/runs/{run_id}/starter-views?language=en")
    vietnamese = client.get(f"/api/runs/{run_id}/starter-views?language=vi")
    assert english.status_code == 200, english.text
    assert vietnamese.status_code == 200, vietnamese.text
    en_card = english.json()["proposals"][0]
    vi_card = vietnamese.json()["proposals"][0]
    assert en_card["question"] == f"How does {en_card['request']['metric']} vary by {en_card['request']['dimension']}?"
    assert vi_card["question"] == f"{vi_card['request']['metric']} thay đổi theo {vi_card['request']['dimension']} như thế nào?"


    assert en_card["request"]["metric"] in en_card["question"]
    assert en_card["request"]["dimension"] in en_card["question"]
    assert "trend by" in en_card["title"].lower()
    assert "xu hướng" in vi_card["title"].lower()


def test_english_chat_response_is_localized_and_table_intent_omits_chart() -> None:
    data = upload_csv("sale_date,net_sales,channel\n2026-01-01,100,Online\n2026-01-02,40,Retail\n")
    run_id = data["run_id"]
    table = client.post(f"/api/runs/{run_id}/chat", json={"message": "Show net sales by channel as a table with rows", "language": "en"})
    assert table.status_code == 200, table.text
    body = table.json()
    assert body["chart"] is None
    assert body["table"]
    assert body["title"] == "Top 2 Net Sales by Channel"
    assert body["answer"] == "I prepared a table of net_sales by channel."
    assert body["insight"] == "Online leads at 100.0."
    assert body["scope"] == "SUM net_sales by channel; 2 results, sorted ranking"
    assert all("Không" not in value and "theo" not in value for value in [body["answer"], body["insight"], body["scope"], *body["caveats"]])

    chart = client.post(f"/api/runs/{run_id}/chat", json={"message": "Show a chart of net sales by channel", "language": "en"})
    assert chart.status_code == 200, chart.text
    chart_body = chart.json()
    assert chart_body["chart"] is not None
    assert chart_body["chart"]["title"] == "Top 2 Net Sales by Channel"
    assert chart_body["chart"]["insight_headline"] == "Online leads at 100.0."


def test_vietnamese_table_intent_omits_chart() -> None:
    data = upload_csv("channel,net_sales\nOnline,100\nRetail,40\n")
    response = client.post(f"/api/runs/{data['run_id']}/chat", json={"message": "Cho bảng doanh thu theo channel dạng bảng", "language": "vi"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["chart"] is None
    assert body["table"]
    assert body["answer"] == "Đã chuẩn bị bảng net_sales theo channel."
    assert "dẫn đầu" in body["insight"].lower()


def test_streaming_exact_top_stores_sales_by_region_uses_net_sales_and_top_three_per_region() -> None:
    data = upload_csv(
        "store,region,net_sales,gross_sales\n"
        "North A,North,100,900\n"
        "North B,North,90,10\n"
        "North C,North,80,800\n"
        "North D,North,70,700\n"
        "South A,South,60,600\n"
        "South B,South,50,500\n"
        "South C,South,40,400\n"
        "South D,South,30,300\n"
    )
    stream = client.post(
        f"/api/runs/{data['run_id']}/chat/stream",
        json={"message": "top 3 stores sales by region", "language": "en"},
    )
    assert stream.status_code == 200, stream.text
    assert "event: completed" in stream.text
    assert '"metric": "net_sales"' in stream.text
    assert '"dimension": "store"' in stream.text
    assert '"secondary_dimension": "region"' in stream.text
    assert '"title": "Top 3 Net Sales by Store per Region"' in stream.text
    assert '"label": "North D"' not in stream.text
    assert '"label": "South D"' not in stream.text
    payload = stream.text.split("event: completed\ndata: ", 1)[1].split("\n\n", 1)[0]
    chart = json.loads(payload)["response"]["chart"]
    assert sum(row["secondary_label"] == "North" for row in chart["rows"]) == 3
    assert sum(row["secondary_label"] == "South" for row in chart["rows"]) == 3


def test_starter_cards_cycle_through_available_metrics() -> None:
    data = upload_csv(
        "sale_date,channel,net_sales,gross_profit,cogs\n"
        "2026-01-01,Online,100,30,70\n"
        "2026-01-02,Retail,40,10,30\n"
    )
    proposals = client.get(f"/api/runs/{data['run_id']}/starter-views?language=en").json()["proposals"]
    metrics = [card["request"]["metric"] for card in proposals]
    assert len(set(metrics)) >= 3



def test_executive_overview_is_deterministic_validated_and_excludes_sensitive_fields() -> None:
    data = upload_csv(
        "sale_date,region,channel,net_sales,cogs,gross_profit,email\n"
        "2026-01-01,North,Online,100,60,40,private@example.test\n"
        "2026-01-02,South,Retail,70,45,25,private@example.test\n"
        "2026-01-03,North,Online,90,55,35,private@example.test\n"
    )
    url = f"/api/runs/{data['run_id']}/executive-overview?language=en"
    first = client.get(url)
    second = client.get(url)
    assert first.status_code == 200, first.text
    assert first.json() == second.json()
    body = first.json()
    assert 1 <= len(body["charts"]) <= 5
    assert {chart["metric"] for chart in body["charts"]} >= {"net_sales", "cogs", "gross_profit"}
    assert all(chart["rows"] for chart in body["charts"])
    assert all(chart["dimension"] != "email" and chart["metric"] != "email" for chart in body["charts"])
    assert "private@example.test" not in str(body)


def test_custom_report_is_run_scoped_idempotent_and_glossary_is_validated() -> None:
    data = upload_csv("store,net_sales,email\nA,100,private@example.test\nB,40,private@example.test\n")
    run_id = data["run_id"]
    assert client.get(f"/api/runs/{run_id}/custom-report").json()["pinned_artifacts"] == []
    artifact = {"artifact_id": "sales-by-store", "chart": {"dimension": "store", "metric": "net_sales"}}
    first = client.post(f"/api/runs/{run_id}/custom-report/artifacts", json=artifact)
    second = client.post(f"/api/runs/{run_id}/custom-report/artifacts", json=artifact)
    assert first.status_code == second.status_code == 200
    body = second.json()
    assert len(body["pinned_artifacts"]) == 1
    assert body["pinned_artifacts"][0]["chart"]["metric"] == "net_sales"
    assert body["glossary"] == [
        {"name": "net_sales", "label": "Net Sales", "description": "Sales revenue after discounts and deductions.", "kind": "num"},
        {"name": "store", "label": "Store", "description": "Inferred cat field from column name and observed values.", "kind": "cat"},
    ]
    assert "email" not in str(body)
    removed = client.delete(f"/api/runs/{run_id}/custom-report/artifacts/sales-by-store")
    repeated = client.delete(f"/api/runs/{run_id}/custom-report/artifacts/sales-by-store")
    assert removed.status_code == repeated.status_code == 200
    assert repeated.json()["pinned_artifacts"] == []


def test_unclear_chat_never_defaults_to_first_metric_or_date_and_top_sites_alias_works() -> None:
    data = upload_csv("event_date,margin,revenue,site,region\n2026-01-01,20,100,A,North\n2026-01-02,10,80,B,North\n")
    run_id = data["run_id"]
    unclear = client.post(f"/api/runs/{run_id}/chat", json={"message": "make a chart", "language": "en"})
    assert unclear.status_code == 200
    assert unclear.json()["mode"] == "clarification"
    sites = client.post(f"/api/runs/{run_id}/chat", json={"message": "top 1 sites revenue by region", "language": "en"})
    assert sites.status_code == 200
    chart = sites.json()["chart"]
    assert chart["metric"] == "revenue" and chart["dimension"] == "site" and chart["secondary_dimension"] == "region"
    assert chart["title"] == "Top 1 Revenue by SITE per Region"
