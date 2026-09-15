"""CAS persistence, migration, and server-owned mutations for report v2."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable, Literal, cast

from fastapi import HTTPException

from report_models import (
    ChartBlock,
    DataTableBlock,
    ReportArtifactSnapshot,
    ReportDocumentV2,
    build_v2_from_legacy,
    validate_report_v2,
)
from report_chart_presentation import build_report_chart_presentation
from report_templates import apply_template
from run_store import ArtifactMalformedError, ArtifactNotFoundError, RunStore

V2_PATH = "custom-report.v2.json"
LEGACY_PATH = "custom-report.json"


def empty_document(run_id: str) -> ReportDocumentV2:
    return ReportDocumentV2(run_id=run_id, updated_at=datetime.now(timezone.utc).isoformat())


def _hash_artifact(chart: dict[str, Any], result: dict[str, Any] | None, dataset_sha256: str) -> str:
    payload = json.dumps({"chart": chart, "result": result, "dataset_sha256": dataset_sha256}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _dataset_sha256(store: RunStore, run_id: str) -> str:
    return hashlib.sha256(store.dataset_path(run_id).read_bytes()).hexdigest()


def _hydrate_presentation(document: ReportDocumentV2) -> ReportDocumentV2:
    """Backfill presentation metadata for reports saved before the parity contract."""
    artifacts = []
    changed = False
    for artifact in document.artifact_library:
        if artifact.result and (not artifact.presentation or not artifact.presentation.get("rows")):
            artifact = artifact.model_copy(update={
                "presentation": build_report_chart_presentation(artifact.result, locale=document.locale),
            })
            changed = True
        artifacts.append(artifact)
    return document.model_copy(update={"artifact_library": artifacts}) if changed else document


def _load_unlocked(store: RunStore, run_id: str) -> ReportDocumentV2:
    try:
        return _hydrate_presentation(validate_report_v2(store.artifact_json(run_id, V2_PATH)))
    except ArtifactNotFoundError:
        pass
    except (ArtifactMalformedError, ValueError) as error:
        raise HTTPException(500, "Saved report is invalid and was not overwritten.") from error
    try:
        legacy = store.artifact_json(run_id, LEGACY_PATH)
    except ArtifactNotFoundError:
        return empty_document(run_id)
    except (ArtifactMalformedError, ValueError) as error:
        raise HTTPException(500, "Saved report is invalid and was not overwritten.") from error
    return _hydrate_presentation(validate_report_v2(build_v2_from_legacy({**legacy, "run_id": run_id})))


def get_document(store: RunStore, run_id: str) -> ReportDocumentV2:
    store.metadata(run_id)
    return _load_unlocked(store, run_id)


def save_document(store: RunStore, document: ReportDocumentV2) -> ReportDocumentV2:
    document = validate_report_v2(document.model_dump(mode="json"))
    with store.locked_artifact(document.run_id, V2_PATH):
        current = _load_unlocked(store, document.run_id)
        if document.revision != current.revision + 1:
            raise HTTPException(409, "This report changed elsewhere. Reload before saving again.")
        now = document.model_copy(update={"updated_at": datetime.now(timezone.utc).isoformat()})
        store.save_artifact_json(document.run_id, V2_PATH, now.model_dump(mode="json"))
        return now


def mutate_document(
    store: RunStore,
    run_id: str,
    expected_revision: int,
    mutation: Callable[[ReportDocumentV2], ReportDocumentV2],
) -> ReportDocumentV2:
    store.metadata(run_id)
    with store.locked_artifact(run_id, V2_PATH):
        current = _load_unlocked(store, run_id)
        if expected_revision != current.revision:
            raise HTTPException(409, "This report changed elsewhere. Reload before saving again.")
        next_document = mutation(current)
        if next_document.run_id != run_id:
            raise HTTPException(422, "Report run does not match the active dataset.")
        if next_document == current:
            return current
        next_document = validate_report_v2(next_document.model_copy(update={"revision": current.revision + 1, "updated_at": datetime.now(timezone.utc).isoformat()}).model_dump(mode="json"))
        store.save_artifact_json(run_id, V2_PATH, next_document.model_dump(mode="json"))
        return next_document


def add_artifact(
    store: RunStore,
    run_id: str,
    expected_revision: int,
    artifact_id: str,
    chart: dict[str, Any],
    result: dict[str, Any],
    *,
    origin: str = "unknown",
    provenance: dict[str, Any] | None = None,
    view: str = "chart",
) -> ReportDocumentV2:
    if view not in {"chart", "table"}:
        raise HTTPException(422, "Artifact view must be chart or table.")
    normalized_origin = cast(Literal["executive_hub", "data_copilot", "legacy", "unknown"], origin if origin in {"executive_hub", "data_copilot", "legacy", "unknown"} else "unknown")
    try:
        dataset_sha256 = _dataset_sha256(store, run_id)
    except FileNotFoundError as error:
        raise HTTPException(404, "Dataset is no longer available for this run.") from error
    normalized_view: Literal["chart", "table"] = cast(Literal["chart", "table"], view)
    presentation = build_report_chart_presentation(result)
    snapshot = ReportArtifactSnapshot(
        artifact_id=artifact_id,
        origin=normalized_origin,
        chart=chart,
        result=result,
        presentation=presentation,
        provenance=provenance or {},
        created_at=datetime.now(timezone.utc).isoformat(),
        artifact_hash=_hash_artifact(chart, result, dataset_sha256),
        dataset_sha256=dataset_sha256,
        view_capabilities=[normalized_view],
    )

    def mutation(current: ReportDocumentV2) -> ReportDocumentV2:
        existing = next((item for item in current.artifact_library if item.artifact_id == artifact_id), None)
        if existing and existing.artifact_hash == snapshot.artifact_hash:
            capabilities = list(dict.fromkeys([*existing.view_capabilities, normalized_view]))
            if capabilities == existing.view_capabilities:
                return current
            return current.model_copy(update={
                "artifact_library": [
                    item.model_copy(update={"view_capabilities": capabilities}) if item.artifact_id == artifact_id else item
                    for item in current.artifact_library
                ]
            })
        library = [item for item in current.artifact_library if item.artifact_id != artifact_id]
        library.append(snapshot)
        return current.model_copy(update={"artifact_library": library})

    return mutate_document(store, run_id, expected_revision, mutation)


def remove_artifact(store: RunStore, run_id: str, expected_revision: int, artifact_id: str) -> ReportDocumentV2:
    def mutation(current: ReportDocumentV2) -> ReportDocumentV2:
        referenced = []
        for block in current.blocks:
            if isinstance(block, (ChartBlock, DataTableBlock)) and block.artifact_id == artifact_id:
                referenced.append(block.block_id)
        if referenced:
            raise HTTPException(409, "Remove the report blocks using this Library item before deleting it.")
        return current.model_copy(update={"artifact_library": [item for item in current.artifact_library if item.artifact_id != artifact_id]})
    return mutate_document(store, run_id, expected_revision, mutation)


def apply_template_cas(store: RunStore, run_id: str, expected_revision: int, template_id: str) -> ReportDocumentV2:
    def mutation(current: ReportDocumentV2) -> ReportDocumentV2:
        return validate_report_v2(apply_template(current.model_dump(mode="json"), template_id))
    return mutate_document(store, run_id, expected_revision, mutation)


def legacy_projection(document: ReportDocumentV2) -> dict[str, Any]:
    artifacts = []
    for item in document.artifact_library:
        result = item.result or {}
        artifacts.append({
            "artifact_id": item.artifact_id,
            "chart": item.chart,
            "annotation": str(item.provenance.get("annotation", "")),
            "title": str(item.provenance.get("title", result.get("title", ""))),
            "scope": str(item.provenance.get("scope", "")),
            "evidence": result.get("evidence", []),
            "warnings": result.get("warnings", []),
            "result": result or None,
        })
    return {
        "run_id": document.run_id,
        "title": document.title,
        "locale": document.locale,
        "layout_blueprint": {"template": next((template for template in ("executive_briefing", "sales_performance_review", "category_division_deep_dive", "weekly_monthly_business_review") if any(page.page_id == template for page in document.pages)), "executive_briefing")},
        "executive_summary": next((getattr(block, "text", "") for block in document.blocks if getattr(block, "type", None) == "text"), ""),
        "sections": [],
        "pinned_artifacts": artifacts,
        "manual_glossary_notes": [],
        "glossary": [],
        "updated_at": document.updated_at,
        "revision": document.revision,
    }
