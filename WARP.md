# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Deal Finder is an AI-powered deal hunting autonomous agent system designed to discover online deals through RSS feeds, estimate prices using ensemble ML models, and send real-time notifications for high-value opportunities.

**Current State**: Early implementation phase - project scaffolding complete with core dependencies installed.

**Target Architecture**: Cloud-native microservices on AWS with Apache technologies for data processing and streaming.

**Current Implementation**:
- Python 3.12 project structure with `pyproject.toml` configuration
- Package management via `uv` with locked dependencies
- Core dependencies installed: FastAPI, Pydantic, boto3, feedparser, redis, httpx
- Development tools configured: pytest, black, ruff, mypy
- Basic source structure created (`src/dealfinder/`)
- Test framework initialized
- **Terraform infrastructure** configured with modular architecture for cost-effective deployment

## Architecture Context

This is a **multi-agent AI system** with the following key components:

### Agent Architecture
- **ScannerAgent**: Scrapes RSS feeds for deals
- **EnsembleAgent**: Aggregates price estimates from multiple models (Specialist, Frontier, Neural Network)
- **MessagingAgent**: Generates personalized notifications using Claude API
- **AutonomousPlanningAgent**: Orchestrates the workflow

### Orchestration Pattern
The system uses **AWS Step Functions** to coordinate a pipeline:
```
Scan → Filter → Parallel Price Estimation → Ensemble Weighting → Evaluate Discount → Notify (if threshold met)
```

### Data Flow
- **Streaming**: Apache Kafka (AWS MSK) with topics: `deals.raw`, `deals.parsed`, `deals.evaluated`, `deals.opportunities`, `notifications.outbound`
- **Storage**: AWS OpenSearch (vector DB), RDS Aurora (relational), DynamoDB (state), S3 (archive)
- **Processing**: Apache Spark on AWS EMR for batch analytics and model training

### Key Design Patterns
1. **Event-Driven Architecture**: All components communicate via Kafka topics
2. **Ensemble ML**: Multiple pricing models combined with weighted averaging
3. **Multi-Channel Notifications**: SNS → Pushover/Email/SMS/WebSocket
4. **Microservices**: Each agent runs as separate AWS Lambda function
5. **Caching Strategy**: Redis for API responses, DynamoDB for state with TTL

## Technology Stack

**Current Planning Stack** (from PRODUCTION_PLAN.md):
- **Backend**: Python 3.12, FastAPI, Pydantic
- **Frontend**: React.js, TypeScript, Material-UI
- **Streaming**: Apache Kafka (AWS MSK)
- **Processing**: Apache Spark (AWS EMR)
- **Vector DB**: AWS OpenSearch with k-NN plugin
- **Orchestration**: AWS Lambda + Step Functions
- **Monitoring**: CloudWatch, Prometheus, Grafana, X-Ray
- **IaC**: Terraform or AWS CDK

**Original Prototype** (referenced in docs):
- Gradio web UI
- OpenAI API (GPT-5.1, GPT-5-mini) → migrating to AWS Bedrock Claude
- ChromaDB (local) → migrating to AWS OpenSearch
- Pushover API for notifications

## Current Dependencies

### Core Production Dependencies
- **fastapi** (0.128.0): Web API framework
- **pydantic** (2.12.5): Data validation and settings management
- **feedparser** (6.0.12): RSS/Atom feed parsing
- **boto3** (1.42.30): AWS SDK for Python
- **redis** (7.1.0): Caching and state management
- **httpx** (0.28.1): Async HTTP client

### Development Tools
- **pytest** (9.0.2) + **pytest-asyncio** (1.3.0): Testing framework
- **black** (26.1.0): Code formatting
- **ruff** (0.14.13): Fast linting
- **mypy** (1.19.1): Type checking

### Package Management
This project uses **uv** for fast, reliable dependency management:
- Dependencies defined in `pyproject.toml`
- Lock file: `uv.lock`
- Install dependencies: `uv pip install -e .`
- Sync environment: `uv pip sync`
- Generate requirements.txt: `uv pip freeze > requirements.txt`

## Development Workflow

### When Implementing Code
The repository is transitioning from planning to implementation:

1. **Agent Implementation**: Each agent should be in a separate Lambda-compatible module with:
   - Clear input/output contracts (Pydantic models)
   - Error handling with retry logic
   - Structured logging (JSON format)
   - OpenTelemetry instrumentation

2. **Step Functions**: State machine definitions should be in AWS ASL (Amazon States Language) JSON format

3. **Kafka Integration**: Use proper schema registry (AWS Glue Schema Registry) and Avro for serialization

4. **Testing**: Each component needs unit tests (pytest) and integration tests against localstack or AWS dev environment

### Infrastructure as Code

**Terraform is the chosen IaC tool** (see TECHNOLOGY_RATIONALE.md for rationale).

#### Terraform Structure
The infrastructure is organized as follows:
```
infrastructure/
├── bootstrap.sh              # One-time backend setup (S3 + DynamoDB)
├── environments/
│   ├── dev/                 # Development environment (cost-optimized)
│   ├── staging/
│   └── prod/
├── modules/
│   ├── networking/          # VPC, subnets (persistent)
│   ├── data/               # S3, DynamoDB, Aurora, OpenSearch, MSK
│   ├── compute/            # Lambda, ECS, Step Functions
│   ├── ml/                 # SageMaker, Bedrock
│   ├── monitoring/         # CloudWatch, Prometheus, Grafana
│   └── security/           # IAM, Secrets Manager, Cognito
└── shared/                  # Common provider and variable configuration
```

#### Key Terraform Principles
1. **Remote State**: All state stored in S3 with DynamoDB locking
2. **Modular Design**: One responsibility per module, reusable across environments
3. **Cost Tagging**: Every resource tagged with `Persistent` (true/false) for lifecycle management
4. **Feature Flags**: Use `enable_*` variables to control expensive resources (MSK, OpenSearch, EMR)
5. **Snapshot Protection**: Critical data resources (Aurora, OpenSearch) have automatic snapshot creation before destroy

#### Cost Management with Terraform
**Destroyable Resources** (can be destroyed when not in use):
- MSK (Kafka): `terraform destroy -target=module.msk` → saves ~$400-600/month
- OpenSearch: `terraform destroy -target=module.opensearch` → saves ~$300-500/month
- ECS Fargate: `terraform destroy -target=module.ecs` → saves ~$200-300/month
- EMR: `terraform destroy -target=module.emr` → saves ~$100-200/month
- NAT Gateway: Set `enable_nat_gateway=false` → saves ~$100/month

**Persistent Resources** (always keep running):
- VPC, Subnets, Route Tables (free tier)
- S3 buckets (minimal cost when idle, lifecycle policies to Glacier)
- DynamoDB tables (on-demand pricing, scales to zero)
- Aurora RDS (use t4g.medium in dev, snapshot to restore)

**Total Potential Savings**: ~60-70% cost reduction by selectively destroying non-persistent infrastructure during idle periods.

#### Working with Terraform
**First-time setup:**
```bash
cd infrastructure
./bootstrap.sh us-east-1 dev          # Create S3 backend
cd environments/dev
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply                        # Start with all expensive resources disabled
```

**Daily development pattern:**
```bash
# Morning: Enable only what you're working on
terraform apply -var="enable_msk=true"  # Only if developing streaming

# Evening: Destroy expensive resources
terraform destroy -target=module.msk
```

**Complete guide**: See `infrastructure/TERRAFORM_GUIDE.md` for comprehensive best practices, workflows, and troubleshooting.

#### Terraform Best Practices for This Project
- ✅ Always use `terraform fmt` before committing
- ✅ Never commit `.tfvars` files (contain environment-specific values)
- ✅ Use `terraform plan` before `apply` to review changes
- ✅ Tag all resources consistently for cost tracking
- ✅ Use feature flags to control expensive resources
- ✅ Enable snapshot protection for data resources
- ❌ Never manually edit `.tfstate` files
- ❌ Never hardcode credentials (use AWS Secrets Manager)
- ❌ Don't create resources outside Terraform once IaC is adopted

## Key Architectural Decisions

### Why AWS + Apache Stack
- **AWS Step Functions**: Visual workflow, built-in error handling, retry logic
- **Apache Kafka (MSK)**: Industry-standard streaming, low latency, durable message storage
- **Apache Spark (EMR)**: Batch processing at scale, feature engineering for ML
- **OpenSearch vs ChromaDB**: Distributed, production-ready vector search with high availability

### Performance Requirements (from docs)
- API P95 latency: < 500ms
- Notification delivery: < 30 seconds from detection
- Throughput: 1000 deals/hour
- Availability: 99.9% uptime SLA

### Cost Optimization Strategy
- Auto-scaling for compute (ECS/Lambda)
- Spot instances for EMR batch jobs
- S3 lifecycle policies (archive to Glacier)
- DynamoDB on-demand for variable traffic
- CloudFront caching for static assets

## Migration Context

This system is being transformed from a **Jupyter notebook prototype** to production. Key migration considerations:

1. **Vector DB Migration**: ChromaDB → OpenSearch requires bulk data export/import with validation
2. **LLM Provider**: OpenAI → AWS Bedrock (Claude) for cost and rate limit management
3. **UI Rewrite**: Gradio → React SPA with WebSocket real-time updates
4. **Deployment**: Local single-instance → Multi-AZ distributed system

## Documentation Standards

### Required Updates After Task/Phase Completion

Whenever you complete any task, update, or phase of work, you MUST update the following documents:

1. **Developer Journal** (`docs/developer_journal.md`)
   - Add new session entry with date, time, phase
   - Document all actions taken with timestamps
   - Record any issues encountered and resolutions
   - Note unexpected findings and lessons learned
   - Include code metrics (lines added, files created)
   - Document architectural decisions made
   - List blockers and how they were resolved
   - Specify next steps and prerequisites

2. **Project Status** (`project-status.md`)
   - Update phase completion percentages
   - Mark completed tasks with ✅
   - Update milestone status
   - Refresh cost estimates if infrastructure changed
   - Update resource allocation tracking
   - Revise risk register if new risks identified
   - Update next actions list
   - Increment version number and add changelog entry

3. **Tests for New Functionality**
   - Create unit tests for all new code (`tests/`)
   - Create integration tests for infrastructure (`tests/infrastructure/`)
   - Run tests and document results
   - Update test coverage metrics
   - Add test documentation to README if needed

4. **Run Validation Tests**
   - Execute `pytest tests/ -v` for unit tests
   - Execute `pytest tests/infrastructure/ -v` for infrastructure tests
   - Verify all tests pass before marking task complete
   - Document any test failures and fixes

### Documentation Templates

**Developer Journal Entry Format:**
```markdown
## Session N: [Phase Name] ([Date])

**Date:** [Date]
**Time:** [Start] - [End] UTC
**Duration:** ~X minutes/hours
**Phase:** [Phase Name]
**Status:** [✅ COMPLETE | ⚙️ IN PROGRESS | ⏸️ BLOCKED]

### Objective
[Brief description of what you're trying to accomplish]

### Actions Taken
#### 1. [Action Name] (X minutes)
[Detailed description]
**Issue Encountered:** [If any]
**Resolution:** [How fixed]
**Lesson Learned:** [Key takeaway]

### Final State
[Summary of what was accomplished]

### Lessons Learned
1. [Lesson 1]
2. [Lesson 2]

### Next Steps
[What comes next]
```

**Project Status Update Format:**
- Update completion percentage: `**Overall Progress:** X% (Y of Z tasks complete)`
- Mark tasks: Change 📝 PENDING to ✅ DONE
- Update milestones table with ACHIEVED status
- Add to Version History table at bottom

### When to Update Documentation

**Always update after:**
- Completing any phase or sub-phase
- Deploying infrastructure changes
- Fixing significant bugs
- Making architectural decisions
- Completing major features
- Resolving blockers
- End of each development session

**Update immediately (same session):**
- Developer journal: Real-time or end of session
- Project status: After phase completion
- Tests: As part of feature implementation

### Testing Requirements

All infrastructure changes require validation tests:

1. **Create test file** in `tests/infrastructure/test_[component].py`
2. **Test structure**:
   - Use pytest fixtures for AWS clients
   - Test resource existence
   - Validate configuration (encryption, tags, etc.)
   - Check security settings
3. **Run tests**: `pytest tests/infrastructure/ -v`
4. **Document results** in developer journal

All application code requires unit tests:

1. **Create test file** in `tests/test_[module].py`
2. **Test coverage**: Aim for >80% coverage
3. **Test types**: Unit, integration, edge cases
4. **Run tests**: `pytest tests/ -v --cov`

## Important Implementation Notes

### State Management
- Use **DynamoDB with TTL** for short-lived deal state (24-48 hours)
- Use **RDS Aurora** for persistent user/deal history
- Implement **idempotency keys** in DynamoDB to prevent duplicate processing

### Error Handling
- All Lambda functions must implement **dead letter queues (DLQ)**
- Step Functions should have **exponential backoff** retry strategies (3 attempts)
- Kafka consumers must handle **poison pill messages** and log to error topics

### Security
- **Never hardcode** API keys (OpenAI, Pushover, etc.) - use AWS Secrets Manager
- All services communicate within **private VPC subnets**
- API Gateway requires **JWT authentication** (AWS Cognito)

### Monitoring Critical Paths
Key metrics to track:
- Kafka lag per consumer group
- Step Function execution success rate
- Deal discovery rate (deals/hour)
- Notification delivery rate
- Model inference latency
- Discount threshold trigger rate

## Reference Documentation

All architectural details are documented in:
- **PRODUCTION_PLAN.md**: Complete system design, component details, migration strategy
- **PROCESS_FLOWS.md**: Visual diagrams of data flows, pipelines, and workflows
- **TECHNOLOGY_RATIONALE.md**: Detailed reasoning for each technology choice with alternatives
- **infrastructure/TERRAFORM_GUIDE.md**: Comprehensive Terraform best practices, workflows, cost management

When making implementation decisions, always reference these documents for:
- Component interactions
- Data schemas
- API contracts
- Deployment procedures
- Monitoring requirements
- Infrastructure management and cost optimization
