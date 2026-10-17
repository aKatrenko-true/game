# Executive review GameHub — 2026-10-17

## Executive summary

Review scope: product delivery, architecture, backend/API, database, CMS/frontend, security, QA/CI, documentation, deployment and operational readiness. Evidence source is repository branch `feature/site-cms-admin`, its code/tests/docs and GitHub Actions metadata. This is a repository review, not a penetration test or production acceptance run.

**Release status: not yet approved.** PR #1 is merged into `feature/postgres-persistence` (merge commit `a7f2dd7653cf88b414c732e16044047df49fc112`). Current hardening commits are on `feature/site-cms-admin`; production deployment of these later commits is not confirmed. Do not assume they are live.

## Findings and actions

| ID | Severity | Area | Finding / risk | Action | Status |
|---|---|---|---|---|---|
| EX-001 | P1 | CMS/frontend security | CMS image values were interpolated into CSS backgrounds using inconsistent filtering; hero image only escaped double quotes. Persisted values should be treated as untrusted. | Added shared `safeImageUrl` allowlist for HTTPS and supported base64 image URLs; reused it for hero and game-card backgrounds; added frontend contract test and QA references. | Fix committed; CI retest pending at report creation |
| EX-002 | P1 | CMS/data integrity | Appearance form wrote each setting via separate PUT requests; a network/validation error could leave a partially updated configuration. | Added bulk `PUT /api/admin/cms/settings`; validates the full set before DB writes; UI now sends one request; added API/frontend tests for atomic validation. | Fix committed; CI retest pending at report creation |
| EX-003 | P1 | Release management | PR #1 has been merged, but manual production smoke checks remain unconfirmed; subsequent hardening commits are on the feature branch. Risk of confusing merged code, branch state and deployed state. | Keep deployment status separate from CI; require latest-commit CI and targeted live smoke before declaring release ready. | Open; no production change performed by this review |
| EX-004 | P1 | QA coverage | Several test cases remain broad/planned: no exact data/step-level expected result, some expectations depend on unspecified contracts, and evidence names do not necessarily correspond to attached artifacts. | Added/updated focused security and atomic-settings cases, traceability and regression entries. Full normalization of the entire legacy suite remains outstanding. | Partial remediation |
| EX-005 | P1 | Security/abuse prevention | Admin shared-password endpoints and account registration/login do not show an application-level rate-limit mechanism in the reviewed code. Repeated attempts may consume resources or facilitate password guessing. | Record as security follow-up; implement rate limiting at a trusted edge/application layer with tests before public production use. Not changed here because a safe distributed limit requires an explicit deployment architecture. | Open |
| EX-006 | P1 | Data protection / operations | CMS images are stored as base64 data URLs in the relational database. This inflates database and backup size; README explicitly notes no automated media backup. | Existing limitation remains; plan object storage and documented restore-tested backups before scale or production-critical content. | Open |
| EX-007 | P1 | Recovery / operations | No draft/publish workflow, content version history or rollback for CMS edits. A mistaken save can immediately affect the public site and require manual repair. | Add a versioning/rollback backlog item and require a backup/restore procedure before business-critical use. | Open |
| EX-008 | P2 | Architecture | `PostgresConnection` translates SQLite-flavoured SQL using string replacements and a custom cursor shim. This is a compatibility layer with migration/SQL edge-case risk. | Add contract/integration coverage for each translated SQL pattern; consider dialect-specific repository functions or SQLAlchemy as a separately scoped refactor. | Open |
| EX-009 | P2 | Startup/reliability | Database initialization is invoked at module import and again in FastAPI lifespan. This can cause redundant startup work and makes import-time database availability a test/deployment concern. | Review initialization lifecycle and move side effects to a single controlled startup path after confirming compatibility with current deployment/tests. | Open; not changed without full lifecycle test |
| EX-010 | P2 | Product scope | CMS supports the main hero, settings, some sections and game images, but not all existing homepage components; no drafts/versioning and no dedicated media storage. | Keep these limitations visible in release notes and backlog; do not present CMS as a full visual site builder. | Documented limitation |
| EX-011 | P2 | Accessibility/responsive | Responsive, keyboard and real-device behavior are not independently confirmed by repository CI alone. | Keep manual desktop/mobile/keyboard checks as Not Run until actually performed; capture real evidence. | Open |
| EX-012 | P2 | PWA/production | Historical Service Worker/cache behavior has no current independent retest evidence. | Run cache-update/offline checks against the deployed commit after release candidate is selected. | Historical / Retest required |

## What was changed in this review

- Restored the original 493-line user-provided QA master prompt and repaired the operational QA instruction file.
- Hardened CMS image URL validation before CSS interpolation.
- Changed appearance settings to a single validated bulk update rather than independent sequential writes.
- Added API tests for invalid bulk updates and admin access, frontend contract tests, a test case, traceability rows, regression checklist entries, and bug reports GH-BUG-008 / GH-BUG-009.
- Kept production untouched.

## CI and verification

At the time this report was authored, relevant GitHub Actions jobs were still running for the latest code changes. Therefore the code changes above are **implemented but not yet verified by a completed CI run** in this report. Latest branch/run status must be refreshed before approving a release.

- Branch: `feature/site-cms-admin`
- Base/deploy branch recorded in PR #1: `feature/postgres-persistence`
- PR #1 merge commit: `a7f2dd7653cf88b414c732e16044047df49fc112`
- Production smoke for latest hardening commits: **Not Run / not confirmed**.

## Release gate

Do not mark release-ready until:
1. API/CMS tests, PostgreSQL integration tests, Python compile, JavaScript syntax and Playwright browser tests pass on the exact candidate commit.
2. Review the changed files and test logs, including any failures and warnings.
3. Run targeted live smoke on the intended deployment: CMS login/denial, create/update/persistence, invalid bulk settings remain unchanged, image URL rendering, hidden content, public homepage, API health and main catalog flows.
4. Confirm branch/commit actually deployed, database available, and backup/restore approach understood.
5. Record screenshots/logs only when they exist; otherwise retain Not Run / Blocked.
6. Create a follow-up PR for post-merge hardening if the base/deploy branch does not already contain these commits. Do not silently deploy from the feature branch.

## Next priorities

- P0: refresh CI status for latest commit and correct any failing test or contract.
- P1: create/review follow-up PR for post-merge fixes; add rate limiting and backup/versioning plan.
- P1: finish test-case normalization and verify screenshot references.
- P2: lifecycle cleanup and database abstraction review.
- P2: manual responsive/accessibility/PWA regression on the actual candidate deployment.
