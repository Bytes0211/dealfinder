# Developer's Journal – Deal Finder Production Migration

**Project:** Deal Finder — AI-Powered Deal Hunting System  
**Engineer:** scotton  
**Initiated:** January 21, 2026  
**Completion:** March 12, 2026  
**Phases Delivered:** 1 – 7 (Infrastructure through Watchlist Agent)

---

## Phase Summary

| Phase | Date Range        | Highlights                                                   | Status | Key Outcomes |
|-------|-------------------|--------------------------------------------------------------|--------|--------------|
| 1     | Jan 21 – Jan 22   | Terraform bootstrap, VPC + networking, monitoring baseline   | ✅      | 47 AWS resources, CI/CD skeleton, $4–10/mo baseline |
| 2     | Feb 17 – Feb 18   | Aurora schema, repositories, embeddings, OpenSearch module   | ✅      | Async data layer, Alembic migrations, 120 unit tests |
| 3     | Feb 24 – Feb 28   | Scanner/Evaluator Lambdas, Step Functions pipeline           | ✅      | RSS ingestion, Bedrock pricing, pipeline alarms |
| 4     | Mar 1 – Mar 3     | Messenger Agent, SES/SNS notifications, FastAPI surface      | ✅      | REST API, notification preferences, auth guardrails |
| 5     | Mar 4 – Mar 7     | Integration testing, prod deployment procedures, dashboards  | ✅      | End-to-end smoke suite, cost/uptime dashboards |
| 6     | Mar 8 – Mar 9     | React SPA, Cognito Hosted UI, API Gateway integration        | ✅      | Frontend deploy pipeline, JWT auth, watchlist UX |
| 7     | Mar 10 – Mar 12   | WatchlistAgent, Tavily integration, trend enrichment         | ✅      | Proactive discovery, deduped notifications, trend data |

## AGENTS Guidance Snapshot (Mar 7, 2026 UTC)
- Status: Phase 7 live; WatchlistAgent on a 30-minute EventBridge cadence with Tavily + Bedrock trend enrichment.
- Frontend Sessions 13–14: Matched Deals feed exposes per-watchlist filters; Preferences page email opt-in gates SES dispatch.
- Bedrock governance: `config/bedrock_models.json` is the single source; current model `anthropic.claude-3-haiku-20240307-v1:0`, upgrade path `us.anthropic.claude-3-5-haiku-20241022-v1:0` after agreement acceptance.

---


## Phase 1 – Infrastructure Foundation (Jan 21 – Jan 22)

### Scope
Bootstrap Terraform backend, establish dev VPC, shared storage, DynamoDB, and monitoring/CI scaffolding.

### Key Activities
- Corrected S3 lifecycle JSON casing (`ID` vs `Id`) in bootstrap script.
- Deployed networking module: 3 public + 3 private subnets across AZs, VPC endpoints for S3/DynamoDB (NAT avoided to cut $100/mo).
- Created S3 buckets (data lake, models, backups) with lifecycle + encryption; DynamoDB tables with TTL for deal state, agent state, and user sessions.
- Authored monitoring module: centralized log groups, cost anomaly detection, SNS alarm topic, dashboard.
- Built GitHub Actions CI (lint/test/security) and CD pipelines (Terraform apply + Lambda deploy stubs); configured Dependabot.

### Validation
- `terraform fmt`, `validate`, `plan`, `apply` (47 resources).
- Manual smoke checks: VPC reachability, endpoint access, log delivery.
- CI dry run locally (`act`) to verify workflow syntax.

### Lessons
- Enforce consistent AWS parameter casing.
- Add explicit `filter {}` in S3 lifecycle rules for provider ≥5.0.
- Feature flags (`enable_*`) keep idle spend <$10/mo.

---

## Phase 2 – Data & Search Layer (Feb 17 – Feb 18)

### Scope
Introduce Aurora schema, repositories, Alembic migrations, OpenSearch ingestion, embedding service.

### Key Activities
- Modeled 5 core tables (Deal, DealSource, User, PriceEstimate, Notification) with SQLAlchemy 2.0 patterns.
- Implemented repository layer with async session patterns, `selectinload`, and SAVEPOINT retry helpers.
- Set up Alembic migrations with env hook to reuse async engine; added migration runner Lambda.
- Added OpenSearch module (k-NN index), embedding provider abstraction (OpenAI + mock), and bulk sync job.
- Extended test suite: SQLite adapters for JSONB/UUID, 120 repository + model tests.

### Validation
- `uv run pytest tests/unit/db tests/unit/data -q`.
- `alembic upgrade head` (dev) via runner script; rollback tested.
- OpenSearch mapping smoke test with dev credentials (manual, one-off).

### Lessons
- Keep decimal precision when bridging Postgres ↔ Python (no float casts).
- Provide helper `values_callable` for enums to avoid uppercase `.name` mishaps.

---

## Phase 3 – Core Pipeline (Feb 24 – Feb 28)

### Scope
Deliver RSS ingestion (ScannerAgent), Bedrock pricing (EvaluatorAgent), Step Functions orchestration, SQS wiring.

### Key Activities
- ScannerAgent: RSS fetch via `run_in_executor`, SHA-256 fallback external IDs, raw data capture, dedupe stats.
- EvaluatorAgent: prompt sanitization, inference logging, discount calc with fail-fast for missing prices, high value marking.
- Step Functions ASL: Map state with retries/catches, notification queue integration, metrics.
- Terraform pipeline module: Lambda roles, EventBridge schedule, SQS DLQs, alarms.
- Added deterministic hash dedupe test, Bedrock prompt/response tests, Step Functions validation.

### Validation
- `uv run pytest tests/unit/agents -q` (36 new tests).
- Step Functions local test harness (mock RSS + stub Bedrock).
- Terraform `plan/apply` in dev; checked CloudWatch alarms.

### Lessons
- Always wrap blocking I/O in executor to avoid event loop stalls.
- Use `Fail` states with Error/Cause to surface pipeline issues to alarms.
- Document reserved queues to avoid “orphaned” resource confusion.

---

## Phase 4 – Notifications & API (Mar 1 – Mar 3)

### Scope
Introduce MessengerAgent, SES/SNS fan-out, email opt-in, REST API (FastAPI + Cognito integration), notification preferences.

### Key Activities
- MessengerAgent uses Bedrock for copy, respects `notification_preferences.email`, dedupes via DynamoDB state.
- SES templates, sandbox verification, SNS topic + SQS subscriber wiring.
- FastAPI app: deals, users, preferences, watchlist matches; dependencies guard asynchronous session usage.
- JWT verification (Cognito Hosted UI), “opt-in” preference toggles, API Gateway integration.
- Added API tests: health, deals list/top/detail, preference updates with opt-in gating.

### Validation
- `uv run pytest tests/unit/api tests/unit/notifications -q`.
- Manual SES sandbox send, CloudWatch log checks.
- Local FastAPI smoke via `uvicorn` behind Cognito tokens (dev pool sample).

### Lessons
- Gate SES on opt-in flag to avoid sandbox rejection, document for future.
- Keep response times <1s P95 with caching and limited eager loads.

---

## Phase 5 – Integration, Observability, Production Runbook (Mar 4 – Mar 7)

### Scope
Harden entire stack for production: run integration tests, finalize dashboards, implement deployment scripts, backup strategy.

### Key Activities
- End-to-end pytest suite (`tests/integration/test_core_pipeline.py`) covering RSS → notification path with moto stubs.
- Added deployment scripts: `deploy-api-lambda.sh`, `run-migrations-lambda.sh`, frontend build pipeline.
- CloudWatch dashboard enhancements: pipeline success/failed counts, DLQ depth widgets, cost monitor.
- Documented rollback/runbooks, Slack alerts hooking into SNS topic.
- Tuned log retention & metric filters; cost forecast for full stack (~$420/mo with current flags).

### Validation
- `uv run pytest tests/integration -q`.
- Smoke test after deployment scripts (dev env).
- Manual CloudWatch alarm tests (set thresholds).

### Lessons
- Observability first: treat dashboards/alerts as IaC.
- Document rollback triggers (latency, error rates) before going live.

---

## Phase 6 – Frontend & Cognito Hosted UI (Mar 8 – Mar 9)

### Scope
Deliver React SPA (Vite + TanStack Query), integrate Cognito Hosted UI, wire API Gateway + CloudFront.

### Key Activities
- Implemented Pages: Feed/Matched Deals, Search, Preferences, Watchlist matches with sticky lists.
- Added Cognito Hosted UI integration, JWT parsing, token expiry guard.
- Axios API client with TanStack Query hooks, consistent error surface.
- Terraform frontend module: S3 hosting, CloudFront distribution, OAI, outputs.
- GitHub Actions for SPA build + S3 sync via OIDC.

### Validation
- `npm run test` (component/unit), manual e2e smoke using Cognito user.
- `aws cloudfront create-invalidation` via CD pipeline after deploy.
- Verified watchlist filter toggle, preference save.

### Lessons
- Expose API error detail to UI; ensure consistent toast handling.
- Pre-populate preferences from API to avoid double-submit issues.

---

## Phase 7 – WatchlistAgent & Trend Enrichment (Mar 10 – Mar 12)

### Scope
Automate proactive discovery with Tavily + Bedrock trend extraction, dedupe notifications, handle race conditions.

### Key Activities
- WatchlistAgent Lambda reads saved watchlist queries, Tavily search, Bedrock trend enrichment (8 fields in `raw_data`).
- Debounced notifications: DynamoDB hash on `user_id + watchlist_id + day`.
- Fixed race condition where concurrent watchlist saves triggered HTTP 500 (transaction isolation + unique constraint guard).
- Added trend logging, metrics for watchlist coverage; pipeline summary agent handles “no deals” notifications.
- Updated developer journal & performance targets, refined cost estimates.

### Validation
- `uv run pytest tests/unit/agents/test_watchlist.py` (new cases), regression on scanner/evaluator.
- Integration run with synthetic Tavily mock; manual CloudWatch log verification.
- EventBridge 30-min schedule dry run; DLQ monitors.

### Lessons
- Use `SELECT ... FOR UPDATE` when writing watchlist saves to avoid racing inserts.
- Normalize new watchlist entries before computing dedupe hash.

---

## Session 15b – Match Card Border Fixes (Mar 8, 2026)

### Scope
Fix hot deal card orange borders not rendering, and investigate non-hot card border visibility.

### Key Activities
- Replaced CSS `:has(.deal-card--hot)` selector with direct `match-card--hot` class applied in `FeedPage.tsx` JSX — `:has()` was unreliable across browsers.
- Iterated through multiple CSS approaches: `border-color` (overridden by dark mode), `border` shorthand with hardcoded color (still overridden), finally `outline: 2px solid #ff6b35` with `outline-offset: -2px` — this survived browser dark mode.
- Non-hot card borders (`#bfc5cc` outline) still invisible in both light and dark mode despite same `outline` technique. Created issue `github/ISSUES/006-non-hot-deal-card-border-invisible.md`.
- Cleaned up branches: merged PR #17, deleted `fix/match-card-borders` locally and on remote, reset local `main` to `origin/main`.
- Deployed frontend to S3/CloudFront with invalidation; verified hot deal orange borders in light mode.

### Files Changed
- `frontend/src/index.css` — `.match-card` outline fallback, `.match-card.match-card--hot` outline rule
- `frontend/src/pages/FeedPage.tsx` — conditional `match-card--hot` class on wrapper div
- `github/ISSUES/006-non-hot-deal-card-border-invisible.md` — new issue

### Validation
- Visual verification in light mode: orange borders on all hot deal cards confirmed.
- Dark mode: hot deal borders work; non-hot borders still invisible (deferred to issue #006).

### Lessons
- Browser automatic dark mode can override CSS `border` and `border-color` properties, even with hardcoded colors and high specificity. `outline` is more resilient.
- CSS `:has()` selector is unreliable for cross-browser production use — prefer applying classes directly in JSX.
- Gray-colored outlines may blend with browser-applied dark mode backgrounds; high-contrast colors (like orange) survive.

---

## Testing & Quality Summary

| Suite                                   | Command                            | Result          |
|-----------------------------------------|------------------------------------|-----------------|
| Core unit (agents, data, API, notif)    | `uv run pytest tests/unit -q`      | 317 passed, 41 skipped |
| Regression (pipeline smoke)             | `uv run pytest tests/regression -q` | 3 passed        |
| Integration (pipeline, notifications)   | `uv run pytest tests/integration -q` | 18 passed       |
| Frontend unit                           | `npm run test`                     | All green       |
| Terraform validation                    | `terraform fmt`, `validate`, `plan` | Clean           |
| Manual smoke                            | Step Functions, SES, Tavily mocks  | Success         |

> Last comprehensive test suite run: March 12, 2026 (`317 passed, 41 skipped; regression suite 3 passed`). Regression pipeline smoke suite (`uv run pytest tests/regression -q`) now runs as part of our release verification checklist.

---

## Open Risks & Mitigations

- **Bedrock throttling** – Mitigated with exponential backoff + retry jitter; monitor `bedrock_throttle_count`.
- **Watchlist race regression** – Added integration regression test; monitor DynamoDB conditional failure metrics.
- **SES sandbox** – Production access still pending; keep verified recipients list synced.

---

## Next Steps / Future Enhancements

1. Confirm Bedrock model access aligns with AGENTS.md guidance: accept the Claude 3.5 Haiku agreement, update `config/bedrock_models.json`, and redeploy affected Lambdas before scaling notifications.
2. Follow AGENTS documentation standards after each phase: update `developer/project-status.md`, ensure `uv run pytest tests/ -v` passes, and append changelog entries.
3. Roadmap: **Phase 8 (Deferred):** Production SES access with SMS rollout; **Phase 9:** Data retention automation, S3 partitioning, and Athena analytics; **Phase 10:** ML-driven deal ranking and reinforcement learning feedback loop.

---

## Appendix – Command Quick Reference

```bash
# Run all Python tests
uv run pytest tests/ -q

# Run integration-only tests
uv run pytest tests/integration -q

# Frontend build & test
npm install
npm run test
npm run build

# Deploy API Lambda (prod)
./scripts/deploy-api-lambda.sh prod

# Apply Terraform changes (dev)
cd infrastructure/environments/dev
terraform fmt && terraform validate && terraform plan
terraform apply

# Frontend deploy (GitHub Actions handles S3 sync)
git push feature-branch
```

---

*Journal maintained and rewritten March 12, 2026 to summarize Phases 1–7.*