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
| P6 | Full quality gate and authenticated DEV release | ✅ | Full pytest/lint/build/local E2E + authenticated DEV browser and export smoke pass |
| Scope | Keep existing Executive Hub, Copilot, Deep Dive behavior unchanged except report integrations | ✅ | Existing suite remains green |

## P0 checklist

- [x] Add JSON-safe serialization at report persistence/export boundaries.
- [x] Return structured JSON for unhandled API errors without leaking internals.
- [x] Add shared frontend response parser; preserve draft/run/tab and offer Retry.
- [x] Cover date serialization and text/plain 500 retry regressions.
- [x] Run focused backend/frontend/browser gates.
- [x] Commit and push verified P0.

## Later phases

- [x] P1 domain/migration/API
- [x] P2 library integration
- [x] P3 canvas builder
- [x] P4 templates
- [x] P5 export
- [x] P6 full QA and DEV deploy

## Final verification evidence

- Python suite: `112 passed` with local auth/source environment unset.
- TypeScript lint, production build, Python compile, and `git diff --check`: pass.
- Local Playwright: 6 report/workspace/layout tests passed.
- Authenticated DEV lifecycle Playwright: 1 passed.
- Authenticated DEV report smoke: v2 title/block persistence, template pages, exact-revision HTML export, and persisted API document passed.
- DEV release SHA: `d9967c45f07150dc5a3737dff3af42117939a42f`.
