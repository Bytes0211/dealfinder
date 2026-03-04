# Deal Finder

> AI-Powered Deal Hunting Autonomous Agent System

An intelligent multi-agent system that discovers online deals through RSS feeds, estimates prices using AWS Bedrock (Claude), and delivers real-time notifications for high-value opportunities. Built serverless on AWS by a solo developer.

## Project Status

**Current Phase:** Phase 3 Complete — Core Pipeline Implemented | Ready for Phase 4

**Scope:** 5 phases / 10 weeks | Serverless-first | Target cost: $200-500/month

See [developer/project-status.md](developer/project-status.md) for detailed tracking.

## Architecture

```
RSS Feeds → Lambda (Scanner) → Step Functions → Lambda (Evaluator) → SNS → Pushover/Email
                                                      ↕
                                                Aurora + OpenSearch
                                                      ↕
                                                Bedrock (Claude)
```

### Agent Architecture
- **ScannerAgent**: Scrapes RSS feeds for deals (Lambda)
- **EvaluatorAgent**: Estimates prices via Bedrock, calculates discounts (Lambda)
- **MessengerAgent**: Generates personalized notifications using Claude, dispatches via SNS (Lambda)

### Orchestration
AWS Step Functions coordinates the pipeline:
```
EventBridge (schedule) → Scanner → Evaluate → Decide (discount > threshold?) → Notify → Update State
```

### Data Flow
- **Messaging:** SQS queues with dead letter queues for reliability, SNS for fan-out notifications
- **Storage:** Aurora PostgreSQL (relational), OpenSearch (vector DB with k-NN), DynamoDB (state/cache with TTL), S3 (archives)
- **LLM:** AWS Bedrock (Claude) for price estimation and notification crafting

## Technology Stack

### Backend
- **Language:** Python 3.12
- **API Framework:** FastAPI with Pydantic
- **Compute:** AWS Lambda + Step Functions
- **Package Manager:** uv

### Data Layer
- **Relational DB:** AWS Aurora PostgreSQL Serverless v2
- **Vector Database:** AWS OpenSearch with k-NN plugin
- **NoSQL/Cache:** AWS DynamoDB (with TTL)
- **Object Storage:** AWS S3
- **Messaging:** SQS (queues + DLQ), SNS (fan-out)

### AI
- **LLM:** AWS Bedrock (Claude) for price estimation and notification crafting

### Infrastructure
- **IaC:** Terraform (remote state in S3 + DynamoDB locking)
- **Monitoring:** CloudWatch (logs, alarms, dashboard, cost anomaly detection)
- **Secrets:** AWS Secrets Manager

## Repository Structure

```
dealfinder/
├── AGENTS.md                      # AI agent guidance
├── PRODUCTION_PLAN.md             # System architecture and phase plan
├── PROCESS_FLOWS.md               # Visual workflow diagrams
├── TECHNOLOGY_RATIONALE.md        # Technology selection reasoning
├── developer/
│   ├── developer_journal.md       # Development session logs
│   └── project-status.md          # Project timeline and status
├── infrastructure/                # Terraform IaC
│   ├── bootstrap.sh               # Backend setup script (one-time)
│   ├── environments/dev/          # Dev environment (deployed)
│   └── modules/
│       ├── networking/            # VPC, subnets, VPC endpoints
│       ├── data/                  # S3, DynamoDB, Aurora, OpenSearch
│       ├── monitoring/            # CloudWatch logs, alarms, dashboard
│       └── pipeline/              # SQS, Lambda, Step Functions, EventBridge
├── src/dealfinder/                # Python package
│   ├── agents/
│   │   ├── config.py              # AgentConfig (pydantic-settings)
│   │   ├── bedrock.py             # BedrockPriceEstimator + PriceEstimationResult
│   │   ├── scanner.py             # ScannerAgent Lambda + handler()
│   │   └── evaluator.py           # EvaluatorAgent Lambda + handler()
│   ├── db/
│   │   ├── models.py              # SQLAlchemy ORM models (5 models, 3 enums)
│   │   ├── connection.py          # Async engine and session management
│   │   └── alembic/               # Database migrations
│   ├── data/
│   │   └── repository.py          # Repository pattern (5 repository classes)
│   └── search/
│       ├── client.py              # OpenSearch client (k-NN, bulk, CRUD)
│       ├── embeddings.py          # Embedding service (abstract provider pattern)
│       └── index.py               # Index management and mappings
├── tests/
│   ├── unit/
│   │   ├── agents/                # Agent unit tests (37 tests)
│   │   ├── db/                    # ORM model tests
│   │   ├── data/                  # Repository tests
│   │   └── search/                # OpenSearch/embedding tests
│   └── infrastructure/            # AWS resource validation tests
└── pyproject.toml                 # Dependencies, tool config, build settings
```

## Getting Started

### Prerequisites

- AWS Account with programmatic access
- Terraform 1.14+
- Python 3.12+
- uv package manager

### Development Setup

```bash
# Clone repository
git clone https://github.com/Bytes0211/dealfinder.git
cd dealfinder

# Install dependencies (including dev tools)
uv pip install -e ".[dev]"

# Bootstrap Terraform backend (one-time)
cd infrastructure
./bootstrap.sh us-east-1 dev

# Deploy infrastructure
cd environments/dev
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings
terraform init
terraform plan
terraform apply
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run unit tests only
uv run pytest tests/unit/ -v

# Run infrastructure validation tests
uv run pytest tests/infrastructure/ -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=html
```

## Performance Targets

- **Pipeline reliability:** >95% successful executions
- **API latency:** <1s P95
- **Notification delivery:** <2 minutes from discovery
- **Monthly cost:** <$500

## Cost Management

Feature flags keep idle dev costs at ~$4-10/month:

- `enable_nat_gateway`: false (saves ~$100/month)
- `enable_aurora`: false (saves $50-100/month)
- `enable_opensearch`: false (saves $25-75/month)

**Production target:** $200-500/month

## Roadmap

### Phase 1: Infrastructure Setup (Weeks 1-2) — COMPLETE
- Terraform backend, VPC, networking, S3, DynamoDB
- CloudWatch monitoring (logs, alarms, dashboard, cost anomaly)

### Phase 2: Data Layer (Weeks 3-4) — COMPLETE
- SQLAlchemy ORM models and Alembic migrations
- Repository pattern data access layer
- OpenSearch client with vector search
- Embedding service with provider abstraction

### Phase 3: Core Pipeline (Weeks 5-7) — COMPLETE
- ScannerAgent Lambda (RSS parsing, SHA-256 dedup, async feedparser)
- BedrockPriceEstimator (Claude via boto3, async via run_in_executor)
- EvaluatorAgent Lambda (discount calc, high-value flagging)
- Step Functions state machine (Scan → Map(Evaluate → IsHighValue?) → Notify)
- SQS queues + DLQ alarms + EventBridge schedule (disabled by default)

### Phase 4: Notifications + API (Weeks 8-9) — NEXT
- Messenger Agent Lambda (Bedrock + Pushover)
- SES email + SNS fan-out
- FastAPI REST API + API Gateway + Cognito auth

### Phase 5: Polish + Deploy (Week 10)
- Integration tests (end-to-end)
- Production Terraform environment
- Production deploy + validation

## Documentation

- **[PRODUCTION_PLAN.md](PRODUCTION_PLAN.md)** — System design and migration phases
- **[PROCESS_FLOWS.md](PROCESS_FLOWS.md)** — Visual data flow diagrams
- **[TECHNOLOGY_RATIONALE.md](TECHNOLOGY_RATIONALE.md)** — Technology choice reasoning
- **[developer/project-status.md](developer/project-status.md)** — Progress tracking
- **[AGENTS.md](AGENTS.md)** — AI agent context for this repository
- **[infrastructure/TERRAFORM_GUIDE.md](infrastructure/TERRAFORM_GUIDE.md)** — Terraform best practices

## Not in Scope (Intentionally Removed)

The following were removed during the Feb 2026 scope revision to keep the project realistic for a solo developer. See PRODUCTION_PLAN.md "Future Enhancements" for triggers to re-add.

- Kafka/MSK, Spark/EMR, ECS Fargate, SageMaker
- Apache APISIX, React frontend
- Prometheus/Grafana, ElastiCache

## Security

- **Authorization:** IAM roles for service-to-service
- **Secrets:** AWS Secrets Manager (never hardcoded)
- **Network:** Private VPC subnets for backend services
- **Encryption:** KMS at rest, TLS in transit

## Contact

*To be added*

## License

*To be determined*

---

**Built with** AWS Lambda · Step Functions · Bedrock · Aurora · OpenSearch · Terraform
