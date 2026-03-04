# AGENTS.md

This file provides guidance to AI assistants (Claude Code, Warp, etc.) when working with code in this repository.

## Project Overview

Deal Finder is an AI-powered deal hunting system that discovers deals via RSS feeds, estimates prices using AWS Bedrock (Claude), and sends notifications for high-value opportunities. It's a serverless system on AWS, built by a solo developer.

**Status:** Phase 2 of 5 complete. Infrastructure and data layer are built. Next: core pipeline (Phase 3).

## Architecture

```
RSS Feeds → Lambda (Scanner) → Step Functions → Lambda (Evaluator) → SNS → Pushover/Email
                                                      ↕
                                                Aurora + OpenSearch
                                                      ↕
                                                Bedrock (Claude)
```

**Stack:** Python 3.12, FastAPI, SQLAlchemy (async), Lambda, Step Functions, SQS/SNS, Aurora PostgreSQL, OpenSearch, Bedrock, Terraform, GitHub Actions

**Not in scope (intentionally removed):** Kafka/MSK, Spark/EMR, ECS Fargate, SageMaker, Apache APISIX, React frontend, Prometheus/Grafana, ElastiCache. See PRODUCTION_PLAN.md "Future Enhancements" for triggers to re-add.

### Agent Architecture
- **ScannerAgent**: Scrapes RSS feeds for deals (Lambda)
- **EvaluatorAgent**: Estimates prices via Bedrock, calculates discounts (Lambda)
- **MessengerAgent**: Generates personalized notifications using Claude, dispatches via SNS (Lambda)

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
├── db/
│   ├── models.py          # SQLAlchemy ORM models (5 models, 3 enums)
│   ├── connection.py       # Async engine, session factory, context manager
│   └── alembic/            # Database migrations
├── data/
│   └── repository.py       # Repository pattern (5 repository classes + BaseRepository)
├── search/
│   ├── client.py           # OpenSearch client (k-NN, bulk, CRUD)
│   ├── embeddings.py       # Embedding service (abstract provider pattern)
│   └── index.py            # Index management and mappings
tests/
├── unit/                   # Unit tests organized by module
│   ├── db/test_models.py
│   ├── data/test_repository.py
│   └── search/test_*.py
├── infrastructure/         # Terraform resource validation tests
infrastructure/
├── environments/dev/       # Terraform dev environment
└── modules/                # Terraform modules (networking, data, monitoring)
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
├── environments/dev/         # Dev environment config
└── modules/
    ├── networking/           # VPC, subnets, VPC endpoints
    ├── data/                 # S3, DynamoDB, Aurora, OpenSearch
    └── monitoring/           # CloudWatch logs, alarms, dashboard
```

### Key Principles
- **Remote state** in S3 with DynamoDB locking.
- **Feature flags:** `enable_aurora`, `enable_opensearch`, `enable_nat_gateway` — control cost.
- **Tagging:** All resources tagged with `Project = "dealfinder"`, `Environment`, and `Persistent` (true/false).
- Run `terraform fmt` before committing.
- Never commit `.tfvars` files or manually edit `.tfstate`.
- Never hardcode credentials — use AWS Secrets Manager.

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
- **Run:** `pytest tests/ -v`

## Git Conventions

- Conventional commits: `type(scope): description`
- Types: feat, fix, docs, refactor, test, chore
- Scopes: db, search, agent, api, terraform, lambda, step-functions
- Keep first line under 72 characters, imperative mood
- Only commit when explicitly asked

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
   - Run `pytest tests/ -v` and verify all pass before marking complete

## Key Design Decisions

1. **Serverless-first** — Lambda + Step Functions, not containers. Minimizes ops overhead for solo dev.
2. **SQS/SNS over Kafka** — sufficient at current scale (100-1000 deals/hour), ~$500/mo cheaper.
3. **Bedrock over SageMaker** — single service for all LLM needs, no endpoints to manage.
4. **API-first, no frontend** — REST API via Lambda + API Gateway + Mangum. UI deferred until users need it.
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
| `src/dealfinder/db/models.py` | All 5 ORM models |
| `src/dealfinder/data/repository.py` | All 5 repository classes + BaseRepository |
| `src/dealfinder/db/connection.py` | Async DB engine and session management |
| `src/dealfinder/search/client.py` | OpenSearch client |
| `src/dealfinder/search/embeddings.py` | Embedding provider abstraction |
| `pyproject.toml` | Dependencies, tool config, build settings |
| `infrastructure/environments/dev/` | Terraform dev environment |

## What NOT to Do

- Don't add Kafka, Spark, ECS, SageMaker, or React — these were intentionally removed from scope.
- Don't use synchronous database calls — everything is async.
- Don't bypass the repository layer with raw SQL or direct session queries in business logic.
- Don't hardcode credentials — use Secrets Manager or env vars via pydantic-settings.
- Don't create heavyweight abstractions for things that only happen once.
- Don't add monitoring infrastructure (Prometheus, Grafana) — CloudWatch is sufficient.

## Reference Documentation

| Document | Purpose |
|----------|---------|
| `PRODUCTION_PLAN.md` | System design, component details, migration phases |
| `PROCESS_FLOWS.md` | Visual diagrams of data flows and pipelines |
| `TECHNOLOGY_RATIONALE.md` | Reasoning behind each technology choice |
| `developer/project-status.md` | Current progress and timeline |
| `infrastructure/TERRAFORM_GUIDE.md` | Terraform best practices and workflows |
