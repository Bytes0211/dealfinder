# AGENTS.md

This file provides guidance to AI assistants (Claude Code, Warp, etc.) when working with code in this repository.

## Project Overview

Deal Finder is an AI-powered deal hunting system that discovers deals via RSS feeds, estimates prices using AWS Bedrock (Claude), and sends notifications for high-value opportunities. It's a serverless system on AWS, built by a solo developer.

**Status:** Phase 7 complete and live in production. WatchlistAgent Lambda runs on a 30-minute EventBridge schedule, proactively discovering deals via Tavily search + Bedrock (Claude 3 Haiku) enrichment. SQLEnum casing bug and Bedrock Legacy model bug fixed (Session 12). Bedrock IAM policies updated to support cross-region inference profiles.

**Frontend (Session 13):** "Matched Deals" feed page (renamed from Feed) supports per-watchlist-entry filter toggle (client-side keyword filtering), scrollable deal grid with sticky watchlist section, and consistent page spacing across all pages.

**Current Bedrock model:** `anthropic.claude-3-haiku-20240307-v1:0` (on-demand, agreement accepted)
**Upgrade path:** Accept Claude 3.5 Haiku agreement in Bedrock console → switch to `us.anthropic.claude-3-5-haiku-20241022-v1:0`

## Architecture

```
RSS Feeds → Lambda (Scanner) → Step Functions → Lambda (Evaluator) → SNS → SMS/Email
                                                      ↕
                                                Aurora + OpenSearch
                                                      ↕
                                                Bedrock (Claude)

Tavily → Lambda (API /search) → Bedrock (BedrockSearchExtractor) → SearchResponse

React SPA (CloudFront) → API Gateway → Lambda (FastAPI/Mangum) → Aurora
```

**Stack:** Python 3.12, FastAPI, SQLAlchemy (async), Lambda, Step Functions, SQS/SNS, Aurora PostgreSQL, OpenSearch, Bedrock, Tavily, Terraform, GitHub Actions, React 19 + Vite + TypeScript, Cognito Hosted UI

**Not in scope:** Kafka/MSK, Spark/EMR, ECS Fargate, SageMaker, Apache APISIX, Prometheus/Grafana, ElastiCache. See PRODUCTION_PLAN.md "Future Enhancements" for triggers to re-add.

### Agent Architecture
- **ScannerAgent**: Scrapes RSS feeds for deals (Lambda)
- **EvaluatorAgent**: Estimates prices via Bedrock, calculates discounts (Lambda); returns `matched_feed_pairs` list of all `{user_id, feed_id, feed_name}` pairs that matched this deal
- **PipelineSummaryAgent**: After ProcessDeals Map, aggregates `matched_feed_pairs` from all deals, finds unmatched (user, feed) pairs, enqueues `no_deals_feed` SQS messages with 24h per-pair dedup (Lambda)
- **MessengerAgent**: Generates personalized notifications using Claude, dispatches via SNS (Lambda); handles `no_deals_feed` event_type with `notify_no_deals_feed` (SES only, per-user)
- **WatchlistAgent**: Scheduled (30-min EventBridge) proactive deal discovery — reads all users' saved watchlist queries, calls Tavily search + `BedrockSearchExtractor(include_trends=True)`, persists `Deal` rows with `status=EVALUATED` and 8 trend fields in `raw_data` JSONB (Lambda)

### Orchestration Pattern
AWS Step Functions coordinates the pipeline:
```
EventBridge (schedule) → Scanner → Evaluate → Decide (discount > threshold?) → Notify → Update State
```

### Data Flow
- **Messaging:** SQS queues with dead letter queues for reliability, SNS for fan-out notifications
- **Storage:** Aurora PostgreSQL (relational), OpenSearch (vector DB with k-NN), DynamoDB (state/cache with TTL), S3 (archives)
- **LLM:** AWS Bedrock (Claude) for price estimation and notification crafting

## Project Structure

```
src/dealfinder/
├── agents/
│   ├── config.py           # AgentConfig (pydantic-settings, env_prefix=DEALFINDER_)
│   ├── bedrock.py          # BedrockPriceEstimator, BedrockSearchExtractor
│   ├── scanner.py          # ScannerAgent + Lambda handler
│   ├── evaluator.py        # EvaluatorAgent + Lambda handler; returns matched_feed_pairs
│   ├── pipeline_summary.py # PipelineSummaryAgent + Lambda handler (per-feed no-deals)
│   ├── messenger.py        # MessengerAgent + Lambda handler; notify_no_deals_feed
│   └── watchlist.py        # WatchlistAgent + Lambda handler (Tavily + Bedrock trend discovery)
├── notifications/          # Notification dispatch clients
│   ├── sns.py              # SnsClient — SMS via boto3 SNS
│   └── ses.py              # SesClient — send_email() via boto3 sesv2
├── api/                    # FastAPI REST API + Mangum
│   ├── main.py             # FastAPI app (lifespan) + Mangum handler
│   ├── schemas.py          # Pydantic request/response models
│   ├── deps.py             # get_db(), get_current_user_id() dependencies
│   └── routes/
│       ├── health.py       # GET /api/v1/health
│       ├── deals.py        # GET /deals, /deals/top, /deals/{id}
│       ├── users.py        # POST /users, PUT /users/{id}/preferences, DELETE /users/{id}, GET /users/{id}/watchlist/matches
│       └── search.py       # POST /search — Tavily + Bedrock enrichment
├── db/
│   ├── models.py           # SQLAlchemy ORM models (5 models, 3 enums)
│   ├── connection.py       # Async engine, session factory, context manager
│   └── alembic/            # Database migrations
├── data/
│   └── repository.py       # Repository pattern (5 repository classes + BaseRepository)
└── search/
    ├── client.py           # OpenSearch client (k-NN, bulk, CRUD)
    ├── embeddings.py       # Embedding service (abstract provider pattern)
    └── index.py            # Index management and mappings
tests/
├── unit/
│   ├── agents/             # Agent tests (conftest.py has shared SQLite overrides)
│   │   ├── conftest.py     # @compiles JSONB/UUID overrides for SQLite
│   │   ├── test_bedrock.py
│   │   ├── test_scanner.py
│   │   ├── test_evaluator.py
│   │   ├── test_pipeline_summary.py
│   │   ├── test_messenger.py
│   │   └── test_watchlist.py   # Phase 7
│   ├── notifications/          # Phase 4
│   │   └── test_ses.py
│   ├── api/                    # Phase 4
│   │   ├── conftest.py     # TestClient + in-memory SQLite fixtures
│   │   ├── test_health.py
│   │   ├── test_deals.py
│   │   └── test_users.py
│   ├── db/test_models.py
│   ├── data/test_repository.py
│   └── search/test_*.py
└── infrastructure/         # Terraform resource validation tests
docs/
├── cost_management.md      # AWS cost breakdown and optimization guide
└── USER_GUIDE.md           # End-user API guide
infrastructure/
├── environments/
│   ├── dev/                # Terraform environment (manages all prod AWS resources)
│   └── staging/            # Staging environment
└── modules/
    ├── networking/         # VPC, subnets, VPC endpoints
    ├── data/               # S3, DynamoDB, Aurora, OpenSearch
    ├── monitoring/         # CloudWatch logs, alarms, dashboard
    ├── pipeline/           # SQS, Lambda, Step Functions, EventBridge, IAM
    ├── notifications/      # SNS topic, Messenger Lambda, SQS ESM
    ├── api/                # API Lambda, API GW HTTP API v2, Cognito
    └── frontend/           # S3 + CloudFront static site, OAC
frontend/
├── src/
│   ├── api/                # axios client, typed API wrappers (deals, users, search)
│   ├── auth/               # Cognito Hosted UI auth helpers + JWT decode
│   ├── components/         # NavBar, DealCard, Pagination, ProtectedRoute, InfoTooltip
│   ├── hooks/              # TanStack Query hooks (useSearch, useDeals, useWatchlistMatches, …)
│   └── pages/              # FeedPage, SearchPage, TopDealsPage, PreferencesPage, …
├── public/                 # Static assets
└── dist/                   # Vite build output (deployed to S3/CloudFront)
```

## Code Conventions

### Python
- **Line length:** 100 (configured in pyproject.toml for both ruff and black)
- **Python version:** 3.12 (use modern syntax: `list[str]` not `List[str]`, `X | None` in new code)
- **Async everywhere:** All database operations use async/await with asyncpg. Never use synchronous DB calls.
- **Type hints:** Use throughout. `Mapped[type]` for SQLAlchemy columns, `Optional[type]` for nullable.
- **Logging:** `logger = logging.getLogger(__name__)` at module level. Use f-strings in log messages.
- **Imports:** stdlib, then third-party, then local. Sorted within groups.
- **Package manager:** uv (dependencies in pyproject.toml, lock file: uv.lock)

### Configuration
- All config classes use `pydantic_settings.BaseSettings` with `env_prefix` and `.env` file support.
- Secrets use `pydantic.SecretStr` (e.g., database passwords, API keys).
- Config naming: `DatabaseConfig`, `OpenSearchConfig`, `EmbeddingConfig` — always suffixed with `Config`.

### Database
- **ORM:** SQLAlchemy 2.0 style with `DeclarativeBase`, `Mapped`, `mapped_column`.
- **Primary keys:** UUID (`PGUUID(as_uuid=True)`, `default=uuid4`).
- **Timestamps:** `server_default=func.now()` for `created_at`, add `onupdate=func.now()` for `updated_at`.
- **Flexible fields:** Use `JSONB` for metadata, tags, preferences.
- **Indexes:** Define in `__table_args__` tuple. Name format: `ix_{table}_{column}`.
- **Unique constraints:** Name format: `uq_{table}_{columns}`.
- **Session pattern:**
  ```python
  async with get_async_session() as session:
      repo = DealRepository(session)
      deal = await repo.get_by_id(deal_id)
  ```
  Sessions auto-commit on success, rollback on exception.
- **Concurrent inserts:** Use `async with session.begin_nested()` (SAVEPOINT) around `repo.create()` when a unique-constraint violation from a concurrent request is possible. The SAVEPOINT rolls back only the failed INSERT, leaving the outer transaction healthy for a retry query. Never query on a session after a bare `IntegrityError` without first rolling back or using a SAVEPOINT.

### Repository Pattern
- All data access goes through repository classes in `data/repository.py`.
- Each entity has its own repository class extending `BaseRepository`.
- Repositories take an `AsyncSession` in `__init__`.
- Methods use `session.execute(select(...))` with `result.scalar_one_or_none()` or `result.scalars().all()`.
- Use `selectinload()` for eager loading relationships.
- Use `session.flush()` + `session.refresh()` after mutations (not `session.commit()` — the context manager handles that).

### Search / Embeddings
- `EmbeddingProvider` is an abstract base class. Implementations: `OpenAIEmbeddingProvider`, `MockEmbeddingProvider`.
- `EmbeddingService` is the high-level interface. It takes a config or provider.
- `OpenSearchClient` wraps the opensearch-py client with retry logic.
- Vector dimension: 1536 (OpenAI ada-002 compatible).

## Terraform

### Structure
```
infrastructure/
├── bootstrap.sh              # One-time backend setup (S3 + DynamoDB)
├── environments/
│   ├── dev/                  # Manages all prod AWS resources
│   └── staging/              # Staging environment
└── modules/
    ├── networking/           # VPC, subnets, VPC endpoints
    ├── data/                 # S3, DynamoDB, Aurora, OpenSearch
    ├── monitoring/           # CloudWatch logs, alarms, dashboard
    ├── pipeline/             # SQS queues+DLQs, Lambda, Step Functions,
    │                         # EventBridge schedule, IAM roles
    ├── notifications/        # SNS, Messenger Lambda, SQS ESM, IAM (Phase 4)
    ├── api/                  # API Lambda, API GW HTTP API v2, Cognito (Phase 4)
    └── frontend/             # S3 + CloudFront static site, OAC (Phase 6)
```

### Key Principles
- **Remote state** in S3 with DynamoDB locking.
- **Feature flags:** `enable_aurora`, `enable_opensearch`, `enable_nat_gateway` — control cost.
- **Tagging:** All resources tagged with `Project = "dealfinder"`, `Environment`, and `Persistent` (true/false).
- Run `terraform fmt` before committing.
- Never commit `.tfvars` files or manually edit `.tfstate`.
- Never hardcode credentials — use AWS Secrets Manager.

### Bedrock IAM Pattern
Always use **two ARN resource entries** for `bedrock:InvokeModel` to support both on-demand models and cross-region inference profiles:
```hcl
Resource = [
  "arn:aws:bedrock:*::foundation-model/*",
  "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:inference-profile/*",
]
```
Cross-region inference profiles (e.g., `us.anthropic.claude-3-5-haiku-20241022-v1:0`) use the `inference-profile` ARN with the account ID. On-demand models use the `foundation-model` ARN without account ID. A single-ARN policy will fail for one or the other.

Before using a new Bedrock model, verify `aws bedrock get-foundation-model-availability --model-id <id>` shows `agreementAvailability.status: AVAILABLE`. If `NOT_AVAILABLE`, accept the agreement via: AWS Console → Amazon Bedrock → Model Access.

### Cost Management
Feature flags keep idle costs at ~$4-10/month:
- `enable_nat_gateway`: false (saves ~$100/month)
- `enable_aurora`: false (saves $50-100/month)
- `enable_opensearch`: false (saves $25-75/month)

## Testing

- **Framework:** pytest + pytest-asyncio
- **Async mode:** `asyncio_mode = "auto"` in pyproject.toml (no need for `@pytest.mark.asyncio`)
- **DB tests:** Use in-memory SQLite (`sqlite+aiosqlite:///:memory:`) with `Base.metadata.create_all`.
- **Mocking:** Prefer real implementations (MockEmbeddingProvider, in-memory DB) over unittest.mock patching.
- **Structure:** Tests grouped into classes (`TestDealRepository`, `TestUserRepository`). Each test has a docstring.
- **Assertions:** Plain `assert` statements. Use `pytest.raises()` for exceptions.
- **Run:** `uv run pytest tests/ -v`

## Git Conventions

- Conventional commits: `type(scope): description`
- Types: feat, fix, docs, refactor, test, chore
- Scopes: db, search, agent, api, terraform, lambda, step-functions, frontend
- Keep first line under 72 characters, imperative mood
- Only commit when explicitly asked
- Always include co-author trailer: `Co-Authored-By: Oz <oz-agent@warp.dev>`
- Never commit directly to `main` — all changes go through a feature branch and PR

## Documentation Standards

### Required Updates After Phase Completion

1. **Developer Journal** (`developer/developer_journal.md`)
   - Add session entry with date, time, phase
   - Document actions taken, issues encountered, resolutions
   - Note lessons learned and next steps

2. **Project Status** (`developer/project-status.md`)
   - Update phase completion percentages
   - Mark completed tasks with checkmarks
   - Update milestone status and cost estimates
   - Increment version number and add changelog entry

3. **Tests**
   - Create unit tests for all new code
   - Run `uv run pytest tests/ -v` and verify all pass before marking complete

## Key Design Decisions

1. **Serverless-first** — Lambda + Step Functions, not containers. Minimizes ops overhead for solo dev.
2. **SQS/SNS over Kafka** — sufficient at current scale (100-1000 deals/hour), ~$500/mo cheaper.
3. **Bedrock over SageMaker** — single service for all LLM needs, no endpoints to manage.
4. **API-first** — REST API via Lambda + API Gateway + Mangum. React frontend added as Phase 6 (S3/CloudFront static site + Cognito Hosted UI).
5. **Cost target: $200-500/month** — use feature flags to keep costs down.

### Performance Targets
- Pipeline reliability: >95% successful executions
- API latency: <1s P95
- Notification delivery: <2 minutes from discovery
- Monthly cost: <$500

## Important Files

| File | Purpose |
|------|---------|
| `PRODUCTION_PLAN.md` | Revised architecture and phase plan |
| `developer/project-status.md` | Progress tracking and timeline |
| `src/dealfinder/agents/scanner.py` | ScannerAgent Lambda (RSS → Aurora) |
| `src/dealfinder/agents/evaluator.py` | EvaluatorAgent Lambda (Bedrock → discount); returns `matched_feed_pairs` |
| `src/dealfinder/agents/pipeline_summary.py` | PipelineSummaryAgent Lambda (per-feed no-deals, 24h dedup) |
| `src/dealfinder/agents/messenger.py` | MessengerAgent Lambda (SQS → SNS/SES); `notify_no_deals_feed` |
| `src/dealfinder/agents/watchlist.py` | WatchlistAgent Lambda (Tavily + Bedrock trend discovery) |
| `src/dealfinder/agents/bedrock.py` | BedrockPriceEstimator, BedrockSearchExtractor (`include_trends` flag) |
| `src/dealfinder/agents/config.py` | AgentConfig pydantic-settings (incl. tavily_api_key) |
| `src/dealfinder/notifications/sns.py` | SnsClient (boto3 SNS SMS) |
| `src/dealfinder/notifications/ses.py` | SesClient (boto3 sesv2) |
| `src/dealfinder/api/main.py` | FastAPI app + Mangum Lambda handler |
| `src/dealfinder/api/routes/deals.py` | Deal endpoints (list, top, detail) |
| `src/dealfinder/api/routes/search.py` | POST /search — Tavily + Bedrock enrichment |
| `src/dealfinder/api/routes/users.py` | User CRUD, preferences, watchlist matches (returns `last_scan_at`, `sources_scanned`), delete |
| `src/dealfinder/api/schemas.py` | Pydantic schemas; `DealListResponse` includes `last_scan_at` + `sources_scanned` |
| `src/dealfinder/db/models.py` | All 5 ORM models |
| `src/dealfinder/data/repository.py` | All 5 repository classes + BaseRepository |
| `src/dealfinder/db/connection.py` | Async DB engine and session management |
| `src/dealfinder/search/client.py` | OpenSearch client |
| `src/dealfinder/search/embeddings.py` | Embedding provider abstraction |
| `pyproject.toml` | Dependencies, tool config, build settings |
| `infrastructure/environments/dev/` | Terraform dev environment |
| `infrastructure/modules/pipeline/` | Pipeline Terraform module |
| `infrastructure/modules/notifications/` | Notifications Terraform module |
| `infrastructure/modules/api/` | API + Cognito Terraform module |
| `docs/cost_management.md` | AWS cost breakdown and optimization guide |
| `docs/USER_GUIDE.md` | End-user API and notification guide |

## Deployment

**Deploy API Lambda** (after Python/FastAPI changes):
```bash
./scripts/deploy-api-lambda.sh prod
```

**Run database migrations** (after schema/Alembic changes):
```bash
./scripts/run-migrations-lambda.sh prod
```
This swaps the Lambda handler temporarily to run `alembic upgrade head` inside the VPC
(where it can reach Aurora), then restores the API handler automatically.

**Deploy infrastructure** (after Terraform changes):
```bash
cd infrastructure/environments/dev
terraform apply
```

**Deploy frontend** (after React/Vite changes):
```bash
cd frontend && npm run build
# GitHub Actions (frontend.yml) handles S3 sync + CloudFront invalidation on push to main
```

## What NOT to Do

- Don't add Kafka, Spark, ECS, or SageMaker — these were intentionally removed from scope.
- Don't use synchronous database calls — everything is async.
- Don't call blocking I/O (boto3, feedparser, requests) directly inside `async def` — wrap in `asyncio.get_running_loop().run_in_executor(None, ...)` to keep the event loop responsive.
- Don't bypass the repository layer with raw SQL or direct session queries in business logic.
- Don't hardcode credentials — use Secrets Manager or env vars via pydantic-settings.
- Don't create heavyweight abstractions for things that only happen once.
- Don't add monitoring infrastructure (Prometheus, Grafana) — CloudWatch is sufficient.
- Don't use Step Functions `Pass` states for error paths — use `Fail` states with `Error`/`Cause` so failed executions show up in `ExecutionsFailed` metrics and alerting.
- Don't access ORM relationships lazily in FastAPI route handlers — always use `selectinload()` in the query to avoid `MissingGreenlet` errors in async context.
- Don't use `@app.on_event("startup")` in FastAPI — use the `lifespan` context manager pattern instead.
- Don't write Alembic enum migrations that UPDATE a column before the new enum value exists — cast the column to `text` first, rename/replace the enum, update data, then cast back. PostgreSQL enforces enum constraints on UPDATE as well as INSERT.
- Don't use `SQLEnum(MyEnum)` without `values_callable=lambda obj: [e.value for e in obj]` — the default sends the Python enum `.name` (uppercase) to PostgreSQL, but PostgreSQL enum types store lowercase values. Always add `values_callable` so SQLAlchemy sends `.value` (lowercase) instead of `.name`.
- Don't invoke a Bedrock model via on-demand if it requires an inference profile — models with the `us.` prefix (e.g., `us.anthropic.claude-3-5-haiku-20241022-v1:0`) must be called as cross-region inference profiles. Check `get-foundation-model-availability` before choosing a model ID.
- Don't set Terraform module output-wiring variables to `default = ""` — required infrastructure wiring (secret ARNs, topic ARNs) should have no default so misconfiguration fails at `terraform plan` time rather than silently at Lambda runtime.
- Don't filter `Deal.discount_percentage >= 0` without also allowing NULL — SQL `NULL >= 0` evaluates to NULL (falsy), silently excluding unevaluated deals. Use `OR(discount_percentage IS NULL, discount_percentage >= threshold)` when 0 is a "match everything" sentinel.

## Reference Documentation

| Document | Purpose |
|----------|---------|
| `PRODUCTION_PLAN.md` | System design, component details, migration phases |
| `PROCESS_FLOWS.md` | Visual diagrams of data flows and pipelines |
| `TECHNOLOGY_RATIONALE.md` | Reasoning behind each technology choice |
| `developer/project-status.md` | Current progress and timeline |
| `infrastructure/TERRAFORM_GUIDE.md` | Terraform best practices and workflows |
