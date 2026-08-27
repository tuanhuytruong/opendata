"""Telegram-transport-neutral guided report flow.

This module deliberately does not read a bot token or make Telegram network calls.
A thin python-telegram-bot/webhook transport can pass incoming text/documents to it,
and send its returned messages. Keeping orchestration here makes the workflow fully
testable and ensures no credentials or raw rows are written into conversation text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from fastapi import HTTPException

from main import ChartRequest, DatasetProfile, build_chart, values
from telegram_flow import (
    ReportRun,
    Step,
    add_chart,
    approve_plan,
    cancel,
    choose_chart_count,
    choose_location,
    dataset_ready,
    skip_filter,
)


@dataclass(frozen=True)
class OutgoingMessage:
    text: str
    options: tuple[str, ...] = ()
    report_html: str | None = None


@dataclass
class Conversation:
    run: ReportRun = field(default_factory=ReportRun)
    profile: DatasetProfile | None = None
    chart_specs: list[ChartRequest] = field(default_factory=list)


class TelegramReportService:
    """Maps a constrained text conversation to validated report operations."""

    def __init__(self, report_renderer: Callable[[str, list[ChartRequest]], str]):
        self._conversations: dict[int, Conversation] = {}
        self._report_renderer = report_renderer

    def start_report(self, chat_id: int) -> OutgoingMessage:
        self._conversations[chat_id] = Conversation()
        return OutgoingMessage("Where should I run the analysis?", ("💻 This machine", "⚡ Database"))

    def attach_dataset(self, chat_id: int, profile: DatasetProfile) -> OutgoingMessage:
        conversation = self._require(chat_id)
        dataset_ready(conversation.run)
        conversation.profile = profile
        kinds = {"num": "metrics", "cat": "dimensions", "time": "time fields"}
        summary = ", ".join(f"{sum(column.kind == key for column in profile.columns)} {label}" for key, label in kinds.items())
        return OutgoingMessage(
            f"✅ {profile.file_name}, {profile.row_count:,} rows, {profile.column_count} columns. "
            f"Profile: {summary}. Send `columns`, `values <column>`, a filter later, or `/skip`.")

    def handle_text(self, chat_id: int, text: str) -> OutgoingMessage:
        normalized = text.strip()
        if normalized == "/report":
            return self.start_report(chat_id)
        try:
            if normalized == "/cancel":
                conversation = self._require(chat_id)
                cancel(conversation.run)
                return OutgoingMessage("This report run was cancelled. Send /report to start another.")
            conversation = self._require(chat_id)
            run = conversation.run
            if run.step == Step.LOCATION:
                return self._choose_location(run, normalized)
            if run.step == Step.FILE:
                return OutgoingMessage("Please send a CSV or XLSX file. Database sources are not enabled in this file-MVP yet.")
            if run.step == Step.FILTER:
                return self._handle_filter(conversation, normalized)
            if run.step == Step.CHART_COUNT:
                return self._choose_chart_count(run, normalized)
            if run.step == Step.PLAN:
                return self._handle_plan(conversation, normalized)
            if run.step == Step.BUILDING:
                return OutgoingMessage("Your approved report is currently building.")
            return OutgoingMessage("This run is closed. Send /report to start another.")
        except (ValueError, HTTPException) as error:
            detail = error.detail if isinstance(error, HTTPException) else str(error)
            return OutgoingMessage(f"I could not apply that: {detail}")

    def _choose_location(self, run: ReportRun, text: str) -> OutgoingMessage:
        lookup = {"💻 this machine": "machine", "this machine": "machine", "machine": "machine", "⚡ database": "database", "database": "database"}
        location = lookup.get(text.lower())
        if location is None:
            raise ValueError("Choose This machine or Database.")
        if location == "database":
            return OutgoingMessage("Database sources are not enabled yet. Choose This machine and upload a CSV or XLSX.", ("💻 This machine",))
        choose_location(run, location)
        return OutgoingMessage("Send a CSV or XLSX file (up to 100 MB and 600,000 rows).")

    def _handle_filter(self, conversation: Conversation, text: str) -> OutgoingMessage:
        if text == "/skip":
            skip_filter(conversation.run)
            return OutgoingMessage("How many charts should I plan? Default is 8; choose 1–12 or /skip.")
        if text == "columns":
            assert conversation.profile is not None
            rendered = "\n".join(f"• {column.name} ({column.kind})" for column in conversation.profile.columns)
            return OutgoingMessage(rendered)
        if text.lower().startswith("values "):
            assert conversation.profile is not None
            column = text.split(maxsplit=1)[1].strip()
            found = values(conversation.profile.run_id, column)["values"]
            return OutgoingMessage(f"Values for {column}: " + ", ".join(found))
        return OutgoingMessage("For this MVP, inspect with `columns` or `values <column>`, then use /skip to choose charts. Exact filters are available in the web workspace.")

    def _choose_chart_count(self, run: ReportRun, text: str) -> OutgoingMessage:
        count = None if text == "/skip" else int(text)
        choose_chart_count(run, count)
        return OutgoingMessage(f"I can plan up to {run.chart_limit} charts. Add one with `add <dimension> by <metric>`, then send /ok.")

    def _handle_plan(self, conversation: Conversation, text: str) -> OutgoingMessage:
        if text == "/ok":
            approve_plan(conversation.run)
            assert conversation.profile is not None
            artifact = self._report_renderer(conversation.profile.run_id, conversation.chart_specs)
            conversation.run.step = Step.COMPLETE
            return OutgoingMessage("✅ Your approved report is ready.", report_html=artifact)
        if not text.lower().startswith("add ") or " by " not in text.lower():
            return OutgoingMessage("Use `add <dimension> by <metric>` or /ok.")
        _, expression = text.split(maxsplit=1)
        dimension, metric = expression.split(" by ", maxsplit=1)
        assert conversation.profile is not None
        request = ChartRequest(dimension=dimension.strip(), metric=metric.strip())
        chart = build_chart(conversation.profile.run_id, request)
        add_chart(conversation.run, chart.title)
        conversation.chart_specs.append(request)
        return OutgoingMessage(f"Added: {chart.title}. Plan now has {len(conversation.chart_specs)}/{conversation.run.chart_limit} charts.")

    def _require(self, chat_id: int) -> Conversation:
        if chat_id not in self._conversations:
            raise ValueError("Start with /report.")
        return self._conversations[chat_id]
