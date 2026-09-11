# Custom Report Builder Rework — Execution Kanban

Source of truth: `2026-09-11_145000-custom-report-builder-rework.md`.

| ID | Phase / task | Status | Verify criterion |
|---|---|---|---|
| P0 | JSON-safe report persistence and safe non-JSON error handling | ✅ | Date-scoped pin/save succeeds; plain-text 500 is actionable and retry preserves draft |
| P1 | Canonical v2 report domain, strict validation, CAS migration | ✅ | Contract/migration/concurrency tests pass |
| P2 | Server-validated Artifact Library from Hub and Copilot | ✅ | Persistent reusable chart/table snapshots with provenance |
| P3 | Desktop canvas builder with grid drag/resize/history/autosave | ✅ | Persisted geometry and conflict-safe browser workflow |
| P4 | Four structurally distinct templates | ✅ | Distinct canonical page/block/placement signatures |
| P5 | Exact-revision preview/export and immutable provenance | ✅ | Export matches persisted document/revision |
| P6 | Full quality gate and authenticated DEV release | ✅ local / ⏳ DEV | Local suite and E2E pass; deployed DEV acceptance pending |
| Scope | Keep existing Executive Hub, Copilot, Deep Dive behavior unchanged except report integrations | ✅ | Existing suite remains green |

## P0 checklist

- [ ] Add JSON-safe serialization at report persistence/export boundaries.
- [ ] Return structured JSON for unhandled API errors without leaking internals.
- [ ] Add shared frontend response parser; preserve draft/run/tab and offer Retry.
- [ ] Cover date serialization and text/plain 500 retry regressions.
- [ ] Run focused backend/frontend/browser gates.
- [ ] Commit and push verified P0.

## Later phases

- [ ] P1 domain/migration/API
- [ ] P2 library integration
- [ ] P3 canvas builder
- [ ] P4 templates
- [ ] P5 export
- [ ] P6 full QA and DEV deploy
