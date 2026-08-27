"""Telegram-neutral report-run state transitions.

The transport adapter will call these functions; this keeps the sample conversation
flow testable without requiring a bot token during local development.
"""
from dataclasses import dataclass, field
from enum import StrEnum


class Step(StrEnum):
    LOCATION = "location"
    FILE = "file"
    FILTER = "filter"
    CHART_COUNT = "chart_count"
    PLAN = "plan"
    BUILDING = "building"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


@dataclass
class ReportRun:
    step: Step = Step.LOCATION
    location: str | None = None
    chart_limit: int = 8
    charts: list[str] = field(default_factory=list)


def choose_location(run: ReportRun, location: str) -> ReportRun:
    if run.step != Step.LOCATION or location not in {"machine", "database"}:
        raise ValueError("A report run must choose machine or database first.")
    run.location = location
    run.step = Step.FILE
    return run


def dataset_ready(run: ReportRun) -> ReportRun:
    if run.step != Step.FILE:
        raise ValueError("A dataset can only be attached after choosing a location.")
    run.step = Step.FILTER
    return run


def skip_filter(run: ReportRun) -> ReportRun:
    if run.step != Step.FILTER:
        raise ValueError("Filter can only be skipped after a dataset is ready.")
    run.step = Step.CHART_COUNT
    return run


def choose_chart_count(run: ReportRun, count: int | None) -> ReportRun:
    if run.step != Step.CHART_COUNT:
        raise ValueError("Chart count is not expected yet.")
    run.chart_limit = 8 if count is None else count
    if not 1 <= run.chart_limit <= 12:
        raise ValueError("Choose between 1 and 12 charts.")
    run.step = Step.PLAN
    return run


def add_chart(run: ReportRun, label: str) -> ReportRun:
    if run.step != Step.PLAN:
        raise ValueError("Charts can only be changed while reviewing the plan.")
    if len(run.charts) >= run.chart_limit:
        raise ValueError("Chart limit reached.")
    run.charts.append(label)
    return run


def approve_plan(run: ReportRun) -> ReportRun:
    if run.step != Step.PLAN or not run.charts:
        raise ValueError("A non-empty chart plan is required before building.")
    run.step = Step.BUILDING
    return run


def cancel(run: ReportRun) -> ReportRun:
    if run.step in {Step.COMPLETE, Step.CANCELLED}:
        raise ValueError("This report run is already closed.")
    run.step = Step.CANCELLED
    return run
