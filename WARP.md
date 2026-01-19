# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Deal Finder is an AI-powered deal hunting autonomous agent system designed to discover online deals through RSS feeds, estimate prices using ensemble ML models, and send real-time notifications for high-value opportunities.

**Current State**: Pre-implementation planning phase with comprehensive architecture documentation.

**Target Architecture**: Cloud-native microservices on AWS with Apache technologies for data processing and streaming.

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

## Development Workflow

### When Implementing Code
Since this repository is currently in planning phase, when code is added:

1. **Agent Implementation**: Each agent should be in a separate Lambda-compatible module with:
   - Clear input/output contracts (Pydantic models)
   - Error handling with retry logic
   - Structured logging (JSON format)
   - OpenTelemetry instrumentation

2. **Step Functions**: State machine definitions should be in AWS ASL (Amazon States Language) JSON format

3. **Kafka Integration**: Use proper schema registry (AWS Glue Schema Registry) and Avro for serialization

4. **Testing**: Each component needs unit tests (pytest) and integration tests against localstack or AWS dev environment

### Infrastructure as Code
When creating IaC:
- Use Terraform modules or AWS CDK constructs for each component
- Follow the component structure from PRODUCTION_PLAN.md sections
- Ensure all resources are tagged for cost allocation

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

When making implementation decisions, always reference these documents for:
- Component interactions
- Data schemas
- API contracts
- Deployment procedures
- Monitoring requirements
