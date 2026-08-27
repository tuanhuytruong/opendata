from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from telegram_flow import (  # noqa: E402
    ReportRun,
    Step,
    add_chart,
    approve_plan,
    choose_chart_count,
    choose_location,
    dataset_ready,
    skip_filter,
)


def test_sample_style_run_reaches_building() -> None:
    run = choose_location(ReportRun(), "machine")
    assert run.step == Step.FILE
    run = dataset_ready(run)
    run = skip_filter(run)
    run = choose_chart_count(run, None)
    assert run.chart_limit == 8
    run = add_chart(run, "distribution_channel_name × net_sales")
    run = approve_plan(run)
    assert run.step == Step.BUILDING


def test_plan_enforces_chart_limit() -> None:
    run = choose_chart_count(skip_filter(dataset_ready(choose_location(ReportRun(), "machine"))), 1)
    add_chart(run, "first")
    try:
        add_chart(run, "second")
    except ValueError as error:
        assert "limit" in str(error)
    else:
        raise AssertionError("Expected chart limit to be enforced")
