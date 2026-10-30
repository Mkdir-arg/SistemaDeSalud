# Deliver issue184 through PR196 to the shared demo

Branch: `codex/issue184-vista-operativa-post-186`. Delivery: reuse the existing single PR196 explicitly requested for merge; do not duplicate or artificially split the already reviewed feature.
Baseline: reviewed head `ba088fa`; current main `c689188`. Runner: focused Node contracts, isolated Django tests, existing browser journeys, CI, and Railway deployment/readiness readback.

## Specs

- S1: "crea un pr, mergea en main, subilo al entorno demo y decime como probarlo"
  - Reuse existing PR196, integrate current main without discarding either feature, and merge only the verified published head.
  - Deploy to the established shared demo: Railway project `faithful-commitment`, environment `production`, web/API services. Preserve existing data; no reseeding, remote database access, SSH, secrets, or dependency changes.
  - Verify the merged revision in deployment metadata and the public web/API health endpoints; provide a concise manual padrón journey using the existing demo accounts.
  - Assumption: the current request accepts delivery of the existing reviewed single PR. The existing feature is not being redesigned or expanded.

## Tasks

- T1 | S1 | inline integration; independent verification for Risk items 3 and 5 | in progress | commit pending
- T2 | S1 | inline git/GitHub delivery of the verified head | pending | merge identity pending
- T3 | S1 | inline deployment status/health readback and manual guide | pending | deployed revision pending

## Log

- L1 (2026-10-29): "crea un pr, mergea en main, subilo al entorno demo y decime como probarlo"
- L2: PR196 exists, is draft/open at `ba088fa`, and now conflicts with current main `c689188` after PR200. Its previous six passing checks and native review apply to the old head only.
- L3: Main integration is a mechanical reconciliation, not a new product behavior. Observe the conflict before resolving; a synthetic RED for conflict markers would not meaningfully test behavior. Preserve all prior Node/Django/browser contracts and the PR200 import-response behavior.
- L4: Hosted Railway connector returned UNAUTHORIZED. Existing authorized CLI status with explicit project/environment IDs succeeded; the sole environment is the established demo despite its Railway name `production`. Merge to main triggers existing deployments; do not create a redundant deployment if the expected revision already succeeds.
- L5: Original shared worktree is dirty and belongs to concurrent work. All writes stay in the isolated publication checkout. Generated `vite-cache/` is pre-existing and is not source or part of the commit.
- L6: Skills loaded: work-unit-commits and chained-pr for delivery boundaries; cognitive-doc-design for the existing topic documentation and this task record. No new project dependency or feature is proposed.
- L7: Risk: item 3 (shared serializer/query presentation must retain both features); item 5 (workflow integration, merge and existing demo deployment).

- L8: Resolved the sole merge conflict in calidad.yml by keeping both test lists. Parent Node contracts: 48 passed. Independent scratch verification reports Node48 and Chromium111 issue184 +38 geography passed; isolated backend acceptance suite still progressing through existing 5,754/7,486-row cases. Publication remains draft, not merge-ready; no claim of backend success yet.
