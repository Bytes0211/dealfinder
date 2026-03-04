# Deal Finder - Production Architecture Plan

**Project**: AI-Powered Deal Hunting Autonomous Agent System
**Date**: January 19, 2026
**Revised**: February 18, 2026
**Objective**: Transform educational prototype into a working, deployed deal discovery system on AWS

---

## Executive Summary

This plan outlines the transformation of "Deal Finder" — an AI agent framework that discovers online deals — from a Jupyter notebook prototype into a deployed, serverless system on AWS.

**Current System** (Prototype):
- Gradio web UI
- OpenAI API integrations (GPT-5.1, GPT-5-mini)
- ChromaDB vector store (local persistence)
- RSS feed scraping
- Multi-agent orchestration
- Push notifications (Pushover API)

**Target Production System**:
- Serverless architecture (Lambda + Step Functions)
- Event-driven pipeline with SQS/SNS
- PostgreSQL (Aurora) for persistent storage
- OpenSearch for vector similarity search
- LLM integration via AWS Bedrock (Claude)
- REST API via API Gateway + Lambda
- Infrastructure as Code (Terraform)
- CloudWatch monitoring and alerting

**Design Principles**:
1. **Build what's needed now** — add complexity only when data demands it
2. **Serverless-first** — minimize operational overhead for a solo developer
3. **End-to-end before breadth** — a working pipeline before a polished UI
4. **Cost-conscious** — target $200-500/month, not $2,000+

---

## Architecture Overview

### High-Level Components

1. **Agent Orchestration Layer** (AWS Step Functions + Lambda)
2. **API Layer** (AWS API Gateway + Lambda)
3. **Messaging Layer** (AWS SQS + SNS)
4. **Vector Database Layer** (AWS OpenSearch Service with k-NN)
5. **Storage Layer** (AWS RDS Aurora + DynamoDB + S3)
6. **LLM Layer** (AWS Bedrock — Claude)
7. **Notification Layer** (SNS + Pushover + SES)
8. **Monitoring Layer** (AWS CloudWatch)

### System Flow

```
RSS Feeds
    │
    ▼
┌─────────────────────────────────────────────────────┐
│              STEP FUNCTIONS STATE MACHINE            │
│                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐  │
│  │ Scanner  │ →  │ Evaluator│ →  │  Messenger   │  │
│  │ (Lambda) │    │ (Lambda) │    │  (Lambda)    │  │
│  └──────────┘    └──────────┘    └──────────────┘  │
│       │               │                │            │
└───────┼───────────────┼────────────────┼────────────┘
        │               │                │
        ▼               ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Aurora     │ │  Bedrock     │ │  SNS/SQS     │
│  PostgreSQL  │ │  (Claude)    │ │  → Pushover  │
│  + OpenSearch│ │              │ │  → SES Email │
└──────────────┘ └──────────────┘ └──────────────┘

Trigger: EventBridge (every 5-15 minutes)
API: API Gateway → Lambda (FastAPI via Mangum)
State: DynamoDB (agent state, rate limits, TTL cache)
Storage: S3 (RSS archives, backups)
Monitoring: CloudWatch (logs, metrics, alarms)
```

---

## Component Details

### 1. Agent Orchestration Layer

**Current**: Synchronous, single-threaded agent execution in Jupyter notebook

**Production Solution**:
- **AWS Step Functions**: Orchestrate the deal discovery pipeline
  - State machine for Scanner → Evaluate → Notify workflow
  - Built-in error handling and retry logic with exponential backoff
  - Parallel execution of independent pricing estimates
  - Visual workflow monitoring via AWS Console

- **AWS Lambda Functions**: Individual agent implementations
  - `ScannerAgent`: Fetch and parse RSS feeds, store new deals
  - `EvaluatorAgent`: Price estimation via Bedrock, discount calculation
  - `MessengerAgent`: Craft and dispatch notifications

- **EventBridge**: Schedule pipeline execution every 5-15 minutes

**Workflow**:
```
Start
  → Initialize Context (load state from DynamoDB)
  → Scanner Agent (fetch RSS, filter new deals)
  → For Each Deal:
      → Estimate Price (Bedrock Claude)
      → Calculate Discount
      → If discount > threshold:
          → Messenger Agent (craft message via Claude, send notification)
  → Update State (DynamoDB)
  → End
```

**Implementation Steps**:
1. Extract agent logic into standalone Lambda functions
2. Design Step Functions state machine (ASL JSON)
3. Configure Lambda layers for shared dependencies (SQLAlchemy, httpx)
4. Add EventBridge rule for scheduled execution
5. Configure SQS dead letter queues for failed executions

### 2. API Layer

**Production Solution**: AWS API Gateway + Lambda (FastAPI via Mangum)

**Endpoints**:
- `GET /api/v1/deals` — List deals with filtering and pagination
- `GET /api/v1/deals/{id}` — Get deal details
- `GET /api/v1/deals/top` — High-value deals sorted by discount
- `POST /api/v1/users` — Create user account
- `PUT /api/v1/users/{id}/preferences` — Update notification preferences
- `GET /api/v1/health` — Health check

**Features**:
- JWT authentication via AWS Cognito
- Request validation via Pydantic
- Auto-generated OpenAPI documentation
- Rate limiting via API Gateway usage plans

**Implementation Steps**:
1. Create FastAPI application with route handlers
2. Integrate with existing repository layer
3. Package with Mangum adapter for Lambda
4. Configure API Gateway with stages (dev, prod)
5. Set up Cognito user pool for authentication

### 3. Messaging Layer

**Production Solution**: AWS SQS + SNS

SQS provides decoupled, reliable message passing between pipeline stages. SNS provides fan-out for multi-channel notifications.

**Queues**:
- `deal-processing` — New deals awaiting evaluation
- `deal-processing-dlq` — Failed processing (for investigation)
- `notification-dispatch` — Notifications awaiting delivery
- `notification-dispatch-dlq` — Failed notifications

**SNS Topics**:
- `deal-notifications` — Fan-out to multiple delivery channels

**Why SQS/SNS instead of Kafka**:
- Zero infrastructure to manage (fully serverless)
- Cost: ~$1-5/month vs $400-600/month for MSK
- Sufficient for current throughput (100-1000 deals/hour)
- Native Lambda integration (event source mapping)
- Dead letter queues for reliability
- Can migrate to Kafka later if throughput demands it

**Implementation Steps**:
1. Create SQS queues with appropriate visibility timeout and DLQ
2. Set up SNS topic with subscriptions (SQS, email, Lambda)
3. Implement Lambda consumers with batch processing
4. Configure retry policies and DLQ alerting

### 4. Vector Database Layer

**Current**: ChromaDB with local persistence
**Production Solution**: AWS OpenSearch Service with k-NN plugin

**Status**: ✅ Client and embedding service already implemented in Phase 2

**Features**:
- HNSW algorithm with cosine similarity (1536-dimensional embeddings)
- Hybrid search: vector similarity + full-text + filtering
- Managed service with multi-AZ high availability
- Index snapshots to S3

**Use Cases**:
- Find similar deals for deduplication
- Recommend deals based on user preference embeddings
- Semantic search across deal descriptions

### 5. Storage Layer

**Relational Data — AWS RDS Aurora PostgreSQL (Serverless v2)**:
- Deal metadata and history
- User accounts and preferences
- Price estimates from ML models
- Notification logs
- RSS feed source configuration

**Status**: ✅ SQLAlchemy models, Alembic migrations, and repository layer implemented in Phase 2

**NoSQL Data — AWS DynamoDB**:
- Agent execution state (TTL-enabled)
- Rate limiting counters
- Short-lived deal cache (24-48 hour TTL)

**Status**: ✅ Tables deployed in Phase 1

**Object Storage — AWS S3**:
- Raw RSS feed archives
- Model artifacts
- Backups and data exports

**Status**: ✅ Buckets deployed in Phase 1 with lifecycle policies

### 6. LLM Layer

**Current**: Direct OpenAI API calls (GPT-5.1, GPT-5-mini)
**Production Solution**: AWS Bedrock (Claude)

**Use Cases**:
- **Price Estimation**: Ask Claude to estimate fair market value given product description, brand, category
- **Notification Crafting**: Generate engaging, personalized deal alert messages
- **Deal Summarization**: Extract key attributes from unstructured deal descriptions
- **Category Classification**: Auto-categorize deals from feed data

**Why Bedrock instead of OpenAI + SageMaker**:
- Single service for all LLM needs (no SageMaker endpoints to manage)
- Data stays within AWS (compliance friendly)
- No separate API key management
- Higher rate limits than public OpenAI API
- Cost-effective: pay per token, no idle compute

**Implementation Steps**:
1. Migrate OpenAI calls to Bedrock SDK (boto3)
2. Design prompt templates for each use case
3. Implement response parsing and validation
4. Add fallback logic (retry with smaller model on failure)
5. Monitor token usage and costs via CloudWatch

### 7. Notification Layer

**Channels**:
- **Pushover**: Primary push notification (port from prototype)
- **Email (SES)**: Deal digest and alerts
- **WebSocket**: Real-time updates (future, when frontend exists)

**Flow**:
```
Messenger Agent → SNS Topic → SQS Queue → Lambda Dispatcher
                                              ├→ Pushover API
                                              ├→ SES Email
                                              └→ DynamoDB (log)
```

**Features**:
- User channel preferences (stored in Aurora)
- Rate limiting (max N notifications per hour per user)
- Deduplication (DynamoDB conditional writes, 24-hour window)
- Delivery tracking and retry

**Implementation Steps**:
1. Implement Pushover client (port from prototype)
2. Configure SES for email delivery
3. Create notification dispatcher Lambda
4. Implement user preference filtering
5. Add delivery tracking to notifications table

### 8. Monitoring Layer

**Production Solution**: AWS CloudWatch

**Status**: ✅ Base monitoring deployed in Phase 1 (log groups, alarms, dashboard)

**Metrics**:
- Pipeline execution count and duration (Step Functions)
- Deals discovered per run
- Notification delivery success rate
- API latency and error rate
- Lambda cold starts and duration
- Bedrock token usage and cost
- DLQ message count (alert trigger)

**Alarms**:
- DLQ messages > 0 → SNS alert
- Pipeline failure rate > 10% → SNS alert
- API error rate > 5% → SNS alert
- Monthly cost exceeding budget → Cost anomaly alert

**Why CloudWatch instead of Prometheus + Grafana**:
- Zero infrastructure to deploy and maintain
- Native integration with all AWS services
- Sufficient for a serverless architecture
- Can add Grafana Cloud later if dashboarding needs grow

---

## Security Architecture

### Authentication & Authorization
- **AWS Cognito**: User authentication and JWT token issuance
- **IAM Roles**: Service-to-service authentication (Lambda execution roles)
- **API Gateway Authorizers**: JWT validation on API requests

### Secrets Management
- **AWS Secrets Manager**: Pushover API key, database credentials
- **Systems Manager Parameter Store**: Configuration values
- Automatic rotation for database credentials

### Network Security
- **VPC**: Private subnets for Aurora and OpenSearch
- **Security Groups**: Least-privilege access between services
- **VPC Endpoints**: S3 and DynamoDB access without internet

**Status**: ✅ VPC, subnets, security groups, and VPC endpoints deployed in Phase 1

### Data Security
- Encryption at rest: S3 (SSE-S3), Aurora (KMS), DynamoDB (KMS)
- Encryption in transit: TLS everywhere
- No PII stored beyond email and notification preferences

---

## CI/CD Pipeline

### Source Control
- **GitHub**: Code repository with branch protection
- **Dependabot**: Automated dependency updates

**Status**: ✅ Configured in Phase 1

### Build & Test Pipeline (GitHub Actions)
- Lint (ruff, black)
- Type check (mypy)
- Security scan (bandit)
- Unit tests (pytest)
- Infrastructure validation (terraform validate)

**Status**: ✅ Configured in Phase 1

### Deployment Pipeline
- **Terraform**: Infrastructure changes
- **GitHub Actions**: Lambda function packaging and deployment
- **Stages**: dev → prod (staging added when needed)

**Implementation Steps**:
1. Add Lambda packaging to GitHub Actions workflow
2. Create Terraform modules for Lambda functions and Step Functions
3. Add deployment step with environment variables
4. Configure rollback on failed health checks

---

## Migration Strategy

### Phase 1: Infrastructure Setup (Weeks 1-2) ✅ COMPLETE
- AWS account and organization
- VPC, networking, VPC endpoints
- S3 buckets, DynamoDB tables
- CI/CD pipeline (GitHub Actions)
- CloudWatch monitoring baseline
- **Delivered**: 47 AWS resources, 97 unit tests

### Phase 2: Data Layer (Weeks 3-4) ✅ COMPLETE
- Aurora PostgreSQL Terraform module
- OpenSearch Terraform module with k-NN
- SQLAlchemy ORM models (5 models)
- Alembic migration framework
- Repository pattern data access layer
- OpenSearch client with vector search
- Embedding service with provider abstraction

### Phase 3: Core Pipeline (Weeks 5-7)
Build the end-to-end deal discovery pipeline.

| Task | Days | Dependencies |
|------|------|--------------|
| Scanner Agent Lambda (RSS parsing, deal extraction) | 3 | Phase 2 |
| Bedrock integration (Claude for price estimation) | 2 | Phase 2 |
| Evaluator Agent Lambda (discount calculation, thresholds) | 2 | Scanner + Bedrock |
| Step Functions state machine (Scanner → Evaluate → Decide) | 2 | All agents |
| SQS queues + DLQ configuration | 1 | Terraform |
| EventBridge schedule (trigger every 5-15 min) | 0.5 | Step Functions |
| Integration test with real feeds | 1.5 | All above |

**Deliverables**:
- 3 Lambda functions (Scanner, Evaluator, Messenger stub)
- Step Functions state machine
- SQS queues with DLQ
- EventBridge scheduled rule
- Bedrock integration for price estimation
- Working pipeline: RSS → deals in Aurora

**Success Criteria**:
- Pipeline runs on schedule without errors
- New deals stored in Aurora with price estimates
- Step Functions execution visible in console
- DLQ empty after successful runs

### Phase 4: Notifications + API (Weeks 8-9)
Add notification delivery and a REST API.

| Task | Days | Dependencies |
|------|------|--------------|
| Messenger Agent Lambda (Bedrock message crafting) | 2 | Phase 3 |
| Pushover integration (port from prototype) | 1 | Messenger agent |
| SES email setup and templates | 1 | Messenger agent |
| SNS topic + fan-out to channels | 1 | Pushover + SES |
| FastAPI application (deals, users, preferences) | 3 | Phase 2 repository |
| Mangum adapter + API Gateway deployment | 1 | FastAPI app |
| Cognito user pool + JWT auth | 1 | API Gateway |

**Deliverables**:
- Messenger Agent Lambda with Bedrock integration
- Pushover push notifications working
- SES email notifications working
- SNS fan-out to multiple channels
- FastAPI REST API (6+ endpoints)
- API Gateway with JWT authentication
- Cognito user pool

**Success Criteria**:
- Notifications delivered to Pushover within 2 minutes of discovery
- API returns deal data with proper auth
- User can update notification preferences via API
- Notification deduplication working (no duplicate alerts)

### Phase 5: Polish + Deploy (Week 10)
Harden, test, and deploy to production.

| Task | Days | Dependencies |
|------|------|--------------|
| Integration tests (end-to-end pipeline) | 2 | Phase 4 |
| Terraform production environment | 1 | Phase 4 |
| CloudWatch dashboard (pipeline + API metrics) | 0.5 | Phase 4 |
| Alarm configuration (DLQ, errors, costs) | 0.5 | Phase 4 |
| Deploy to production | 0.5 | All above |
| Smoke test and validation | 0.5 | Deploy |

**Deliverables**:
- Integration test suite
- Production Terraform environment
- CloudWatch operational dashboard
- Alarm and alerting configuration
- Production deployment

**Success Criteria**:
- Pipeline runs in production for 48 hours without errors
- Notifications delivered successfully
- API accessible and authenticated
- Alarms trigger correctly on simulated failures
- Monthly cost < $500

---

## Future Enhancements (Not In Scope)

These are deferred until the core system proves its value and scale demands them:

| Enhancement | Trigger to Add |
|-------------|---------------|
| React frontend / dashboard | Users need a UI beyond API |
| Apache Kafka (MSK) | Throughput exceeds 10K deals/hour |
| Apache Spark (EMR) | Historical data exceeds what Lambda can process |
| SageMaker custom models | Training data collected, model accuracy matters |
| ECS Fargate (API) | Lambda cold starts become unacceptable |
| ElastiCache (Redis) | API cache-hit rate needs improvement |
| Prometheus + Grafana | CloudWatch dashboarding becomes insufficient |
| Mobile app | User demand |
| Multi-marketplace support | Core RSS pipeline proven |
| A/B testing framework | Multiple model variants to compare |

---

## Cost Projection

**Estimated Monthly Costs** (100-1000 deals/hour, initial users):

| Service | Monthly Cost | Notes |
|---------|-------------|-------|
| AWS Lambda | $10-30 | Agent functions + API handlers |
| API Gateway | $5-15 | REST API requests |
| Step Functions | $5-15 | Pipeline orchestrations |
| RDS Aurora Serverless v2 | $50-100 | Scales to zero when idle |
| OpenSearch | $25-75 | Dev: single-node, Prod: multi-AZ |
| DynamoDB | $1-5 | On-demand pricing |
| S3 | $1-5 | RSS archives, backups |
| AWS Bedrock | $50-150 | Claude API calls for estimation + messaging |
| SQS/SNS | $1-5 | Message passing and notifications |
| SES | $1-5 | Email notifications |
| CloudWatch | $5-15 | Logs, metrics, alarms |
| Cognito | $0-10 | Free tier covers initial users |
| Secrets Manager | $2-5 | API keys and credentials |
| **Total** | **$156-435** | |

**Cost Control**:
- Aurora Serverless v2 scales to zero when idle
- Lambda pay-per-invocation (no idle compute)
- Feature flags for expensive resources (OpenSearch, Aurora)
- CloudWatch billing alarms
- DynamoDB on-demand pricing (no provisioned capacity)

---

## Success Metrics

### Technical KPIs
- **Pipeline Reliability**: >95% successful executions
- **API Latency**: <1s P95 (including Lambda cold starts)
- **Notification Delivery**: <2 minutes from discovery
- **Error Rate**: <5% of pipeline runs
- **Monthly Cost**: <$500

### Business KPIs
- **Deal Discovery Rate**: 20-100 new deals/day
- **Notification Relevance**: >80% above discount threshold
- **Cost per Notification**: <$0.10

---

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Bedrock rate limits | HIGH | LOW | Request limit increase, implement backoff |
| Lambda cold starts | MEDIUM | MEDIUM | Provisioned concurrency for API (if needed) |
| Aurora cost overrun | MEDIUM | LOW | Serverless v2 scales to zero, feature flag |
| OpenSearch cost overrun | MEDIUM | MEDIUM | Feature flag, snapshot before destroy |
| RSS feed changes/breakage | MEDIUM | HIGH | Robust parsing, error handling, DLQ |
| Scope creep | HIGH | MEDIUM | This document — stick to the phases |

---

## Technology Stack Summary

- **Runtime**: Python 3.12
- **API Framework**: FastAPI + Pydantic + Mangum
- **ORM**: SQLAlchemy (async) + Alembic
- **Compute**: AWS Lambda
- **Orchestration**: AWS Step Functions
- **Scheduling**: AWS EventBridge
- **Messaging**: AWS SQS + SNS
- **LLM**: AWS Bedrock (Claude)
- **Relational DB**: AWS RDS Aurora PostgreSQL (Serverless v2)
- **Vector DB**: AWS OpenSearch with k-NN
- **NoSQL**: AWS DynamoDB
- **Object Storage**: AWS S3
- **Auth**: AWS Cognito
- **Notifications**: Pushover, AWS SES
- **Monitoring**: AWS CloudWatch
- **IaC**: Terraform
- **CI/CD**: GitHub Actions
- **Package Manager**: uv
