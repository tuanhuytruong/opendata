from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from main import DatasetProfile, build_report  # noqa: E402
from telegram_adapter import TelegramReportService  # noqa: E402


def profile(run_id: str = "a" * 32) -> DatasetProfile:
    return DatasetProfile.model_validate({
        "run_id": run_id,
        "file_name": "sales.csv",
        "row_count": 3,
        "column_count": 2,
        "usable_column_count": 2,
        "columns": [
            {"name": "channel", "kind": "cat", "null_count": 0, "null_ratio": 0, "distinct_count": 2, "description": "Channel"},
            {"name": "net_sales", "kind": "num", "null_count": 0, "null_ratio": 0, "distinct_count": 3, "description": "Sales"},
        ],
        "warnings": [],
        "preview": [],
    })


def test_machine_conversation_reaches_report(monkeypatch) -> None:
    chart_calls = []
    monkeypatch.setattr("telegram_adapter.build_chart", lambda run_id, request: type("Chart", (), {"title": f"SUM {request.metric} by {request.dimension}"})())
    service = TelegramReportService(lambda run_id, charts: "<html>report</html>")
    assert service.start_report(9).options == ("💻 This machine", "⚡ Database")
    assert "Send a CSV" in service.handle_text(9, "This machine").text
    assert "3 rows" in service.attach_dataset(9, profile()).text
    assert "channel (cat)" in service.handle_text(9, "columns").text
    assert "Apply filter" in service.handle_text(9, "net_sales >= 50").text
    assert "Applied filter" in service.handle_text(9, "yes").text
    assert "How many charts" in service.handle_text(9, "/skip").text
    assert "up to 2 charts" in service.handle_text(9, "2").text
    assert "Added" in service.handle_text(9, "add channel by net_sales").text
    assert "Plan (1/2)" in service.handle_text(9, "status").text
    assert "Removed chart" in service.handle_text(9, "remove 1").text
    assert "Added" in service.handle_text(9, "add channel by net_sales").text
    complete = service.handle_text(9, "/ok")
    assert complete.report_html == "<html>report</html>"


def test_rejects_database_and_stale_command() -> None:
    service = TelegramReportService(lambda run_id, charts: "report")
    assert "Start with /report" in service.handle_text(1, "columns").text
    service.start_report(1)
    assert "not enabled" in service.handle_text(1, "Database").text
    assert "Send a CSV" in service.handle_text(1, "This machine").text


def test_renderer_is_not_called_without_approved_chart() -> None:
    service = TelegramReportService(lambda run_id, charts: (_ for _ in ()).throw(AssertionError("must not render")))
    service.start_report(3)
    service.handle_text(3, "machine")
    service.attach_dataset(3, profile())
    service.handle_text(3, "/skip")
    service.handle_text(3, "1")
    assert "non-empty chart plan" in service.handle_text(3, "/ok").text
