# Technology Selection Rationale

**Project**: Deal Finder - AI-Powered Deal Hunting System  
**Date**: January 19, 2026  
**Purpose**: Document the reasoning behind each technology choice in the production architecture

---

## Executive Summary

The Deal Finder architecture prioritizes **scalability**, **reliability**, and **cost-effectiveness** while enabling real-time deal discovery and notification delivery. Technology selections balance managed AWS services (reducing operational overhead) with best-in-class Apache open-source technologies (avoiding vendor lock-in and leveraging proven data processing patterns).

---

## Core Architectural Principles

The technology stack was selected based on these guiding principles:

1. **Cloud-Native First**: Leverage managed services to reduce operational burden
2. **Event-Driven Architecture**: Enable loose coupling and independent scaling
3. **Open Standards**: Avoid vendor lock-in where possible (Apache ecosystem)
4. **Proven at Scale**: Choose technologies with production track records
5. **Cost Optimization**: Balance performance with budget constraints
6. **Developer Experience**: Prioritize tools with strong community support

---

## Technology Decisions

### 1. AWS as Cloud Provider

**Selected**: Amazon Web Services (AWS)

**Alternatives Considered**:
- Google Cloud Platform (GCP)
- Microsoft Azure
- Self-hosted on-premises

**Rationale**:
- **Maturity**: AWS has the most comprehensive service catalog (200+ services)
- **Managed ML Services**: AWS Bedrock provides direct access to Claude models without API rate limits
- **Apache Integration**: Best support for managed Apache services (MSK for Kafka, EMR for Spark)
- **Step Functions**: Superior orchestration service for complex agent workflows
- **Cost Efficiency**: Spot instances and auto-scaling reduce costs for variable workloads
- **OpenSearch Service**: Fully managed vector database with k-NN search

**Trade-offs**:
- ✅ Reduces operational complexity vs. self-hosting
- ✅ Integrated security and IAM
- ⚠️ Potential vendor lock-in (mitigated by using open standards)
- ⚠️ Learning curve for AWS-specific services (Not an issue for me. Maybe for other devs)

---

### 2. Apache Kafka (AWS MSK) - Data Streaming

**Selected**: Apache Kafka on AWS MSK (Managed Streaming for Kafka)

**Alternatives Considered**:
- AWS Kinesis Data Streams
- RabbitMQ
- Apache Pulsar
- Google Cloud Pub/Sub

**Rationale**:
- **Industry Standard**: De facto standard for event streaming (used by LinkedIn, Uber, Netflix)
- **Durability**: Messages persisted to disk with configurable retention (7-30 days)
- **Throughput**: Handles millions of messages per second with horizontal scaling
- **Ecosystem**: Rich connector ecosystem (Kafka Connect) for integration
- **Exactly-Once Semantics**: Critical for preventing duplicate deal notifications
- **Replay Capability**: Can reprocess historical data for debugging or backfill

**Why MSK over Kinesis**:
- Kafka Connect and KSQL provide richer stream processing
- Better support for multi-consumer patterns (different agents consuming same topics)
- Easier to migrate off AWS if needed (portable to any Kafka deployment)
- More mature tooling (Kafka UI, monitoring, client libraries)

**Trade-offs**:
- ✅ Open-source standard (portable)
- ✅ Exactly-once semantics prevent duplicate notifications
- ⚠️ More expensive than Kinesis (~$400-600/month vs ~$200-300/month)
- ⚠️ Requires understanding of Kafka concepts (partitions, consumer groups)

---

### 3. Apache Spark (AWS EMR) - Batch Processing

**Selected**: Apache Spark on AWS EMR (Elastic MapReduce)

**Alternatives Considered**:
- AWS Glue (serverless Spark)
- Apache Flink (stream processing)
- Dask (Python-native)
- Pandas on Lambda

**Rationale**:
- **Unified Analytics**: Single framework for batch processing, SQL, ML, and graph analytics
- **Performance**: In-memory processing 100x faster than Hadoop MapReduce
- **ML Pipeline**: Native support for feature engineering and model training (MLlib)
- **Scale**: Handles terabytes of data for historical deal analysis
- **Cost Efficiency**: EMR Spot instances reduce costs by 70-90%

**Why EMR over AWS Glue**:
- More control over cluster configuration and optimization
- Support for custom libraries and dependencies
- Better for iterative ML training workloads:
  - **Persistent Clusters**: EMR clusters stay alive between jobs, avoiding cold start overhead (5-10 min) on each training iteration
  - **In-Memory Caching**: Can cache training data in memory across multiple epochs using `df.cache()` or `df.persist()`, dramatically speeding up iterative algorithms
  - **Interactive Development**: Support for Jupyter notebooks and Zeppelin for experimenting with model architectures during training
  - **Fine-Grained Resource Control**: Configure exact CPU/memory per executor for memory-intensive ML operations (Glue has fixed worker types)
  - **Example**: Training a neural network pricing model requires 50+ epochs over the same dataset. EMR caches the data once; Glue would reload from S3 each time
- Spark UI for debugging and performance tuning

**Use Cases in Deal Finder**:
1. **Feature Engineering**: Transform raw deal data for ML models
2. **Model Training**: Retrain neural network on historical pricing data (weekly)
3. **Analytics**: Generate aggregated reports on deal trends
4. **Data Quality**: Validate and clean data pipelines

**Trade-offs**:
- ✅ Best-in-class for large-scale data processing
- ✅ Spot instances dramatically reduce cost
- ⚠️ Operational complexity (cluster management)
- ⚠️ Overkill for small datasets (but supports future scale)

---

### 4. AWS OpenSearch - Vector Database

**Selected**: AWS OpenSearch Service with k-NN plugin

**Alternatives Considered**:
- ChromaDB (current prototype)
- Pinecone (SaaS vector DB)
- Weaviate (open-source vector DB)
- pgvector (Postgres extension)
- FAISS (library, not database)

**Rationale**:
- **Hybrid Search**: Combines vector similarity with full-text search and filtering
- **Managed Service**: AWS handles scaling, backups, and high availability
- **Performance**: HNSW and IVF algorithms for approximate nearest neighbor search
- **Integration**: Native integration with AWS services (Lambda, S3, CloudWatch)
- **Cost**: More cost-effective than dedicated vector DB SaaS at scale
- **Proven at Scale**: Used by Amazon.com for product recommendations

**Why OpenSearch over ChromaDB**:
- ChromaDB is single-node and not production-ready for high availability
- OpenSearch scales horizontally across multiple AZ
- Better query language (JSON-based DSL)
- Built-in security, monitoring, and alerting

**Why OpenSearch over Pinecone**:
- Lower cost at scale ($300-500/month vs $1000+/month)
- No vendor lock-in (can self-host OpenSearch)
- Unified platform for logs, metrics, and vectors
- No cold start issues (always warm)

**Trade-offs**:
- ✅ Production-ready with high availability
- ✅ Lower cost than SaaS alternatives
- ⚠️ More complex to configure than Pinecone
- ⚠️ Migration effort from ChromaDB

---

### 5. AWS Step Functions - Agent Orchestration

**Selected**: AWS Step Functions

**Alternatives Considered**:
- Apache Airflow (MWAA)
- Temporal.io
- Celery (Python task queue)
- Custom orchestration with SQS

**Rationale**:
- **Visual Workflows**: State machine diagram makes complex flows understandable
- **Built-in Retry Logic**: Exponential backoff and error handling without code
- **Parallel Execution**: Run multiple pricing models simultaneously (Specialist, Frontier, Neural)
- **Long-Running Workflows**: Can wait for external events or human approval
- **Integration**: Native integration with all AWS services (Lambda, SageMaker, etc.)
- **Observability**: Built-in execution history and CloudWatch integration

**Why Step Functions over Airflow**:
- Serverless (no cluster to manage)
- Sub-second latency for agent workflows (Airflow is batch-oriented with minute-level scheduling)
- Better for event-driven workflows (triggered by deal discovery, not cron)
- Lower operational overhead

**Workflow Example**:
```
Scan Feeds → Filter → [Parallel: Model1, Model2, Model3] → Ensemble → Evaluate → Notify
```

**Trade-offs**:
- ✅ Zero infrastructure management
- ✅ Visual workflow editor simplifies debugging
- ⚠️ AWS-specific (lock-in), though ASL (Amazon States Language) is portable
- ⚠️ Can become expensive at very high volumes (optimized with Express workflows)

---

### 6. FastAPI - Backend Framework

**Selected**: FastAPI (Python 3.12)

**Alternatives Considered**:
- Flask
- Django REST Framework
- Node.js (Express)
- Go (Gin/Echo)

**Rationale**:
- **Performance**: Async/await support with performance comparable to Node.js and Go
- **Type Safety**: Pydantic integration for automatic validation and serialization
- **API Documentation**: Auto-generated OpenAPI (Swagger) documentation
- **Modern Python**: Leverages Python 3.10+ features (type hints, pattern matching)
- **Developer Experience**: Intuitive decorators and dependency injection
- **ML Integration**: Seamless integration with Python ML ecosystem (scikit-learn, PyTorch)

**Why FastAPI over Flask**:
- Async support (Flask requires additional libraries)
- Built-in data validation (reduces boilerplate)
- Better performance (3-4x faster for I/O-bound operations)
- Type hints improve IDE support and catch bugs early

**Why Python over Go/Node**:
- Agent logic, ML models, and data processing are all Python-based
- Single language reduces context switching
- Richer ecosystem for AI/ML tasks

**Trade-offs**:
- ✅ Best Python framework for APIs
- ✅ Excellent documentation and community
- ⚠️ Not as fast as Go for CPU-bound tasks (acceptable for I/O-bound API)

---

### 7. AWS Lambda - Serverless Compute

**Selected**: AWS Lambda Functions

**Alternatives Considered**:
- ECS Fargate (containers)
- EC2 instances
- Kubernetes (EKS)

**Rationale**:
- **Cost**: Pay only for execution time (no idle compute costs)
- **Auto-Scaling**: Automatic scaling from 0 to 10,000+ concurrent executions
- **Integration**: Native integration with Step Functions, API Gateway, S3, etc.
- **Operational Simplicity**: No servers to patch or manage
- **Cold Start Mitigation**: Provisioned concurrency for latency-sensitive paths

**Use Cases in Deal Finder**:
1. **Agent Functions**: Each agent (Scanner, Ensemble, Messaging) as separate Lambda
2. **API Endpoints**: Low-traffic endpoints (user preferences, manual triggers)
3. **Event Processing**: Triggered by S3 uploads, Kafka messages, SNS notifications
4. **Scheduled Tasks**: EventBridge rules trigger periodic scans

**When NOT to Use Lambda**:
- Long-running processes (>15 min) → Use ECS Fargate
- Consistent high traffic → ECS may be more cost-effective
- Complex state management → Step Functions or ECS with persistent connections

**Trade-offs**:
- ✅ Zero infrastructure management
- ✅ Cost-effective for variable workloads
- ⚠️ 15-minute timeout limit
- ⚠️ Cold starts (50-200ms) may impact latency-sensitive paths

---

### 8. React.js + TypeScript - Frontend

**Selected**: React.js with TypeScript

**Alternatives Considered**:
- Vue.js
- Svelte
- Angular
- Gradio (current prototype)

**Rationale**:
- **Ecosystem**: Largest ecosystem of components and libraries
- **Type Safety**: TypeScript catches errors at compile time
- **Component Reusability**: Build once, reuse across web and mobile (React Native)
- **Performance**: Virtual DOM and efficient re-rendering
- **Talent Pool**: Most popular frontend framework (easier to hire)

**Why React over Gradio**:
- Gradio is for prototyping ML apps, not production web apps
- Full control over UX/UI (Gradio is limited)
- Better performance and customization
- Professional appearance for user-facing product

**Supporting Libraries**:
- **Material-UI**: Pre-built components following Material Design
- **Plotly.js**: 3D visualization for vector space explorer
- **React Query**: Server state management and caching
- **WebSocket**: Real-time updates for new deal notifications

**Trade-offs**:
- ✅ Industry-standard framework
- ✅ TypeScript improves code quality
- ⚠️ Larger bundle size than Svelte (mitigated with code splitting)

---

### 9. AWS Bedrock (Claude) - LLM Provider

**Selected**: AWS Bedrock with Claude 3.5 Sonnet

**Alternatives Considered**:
- OpenAI API (current prototype)
- Self-hosted LLaMA
- Azure OpenAI Service
- Google Vertex AI

**Rationale**:
- **Cost**: No additional API fees beyond compute (included in AWS bill)
- **Rate Limits**: Higher throughput than OpenAI public API
- **Latency**: AWS region proximity reduces latency
- **Security**: Data never leaves AWS (compliance friendly)
- **Multi-Model**: Access to Claude, LLaMA, Titan, Mistral in one API

**Why Claude over GPT**:
- Better at following instructions for structured output
- Longer context window (200K tokens)
- More cost-effective for generation tasks
- Excels at creative, personalized notification messages

**Use Cases**:
- Generate engaging notification messages
- Summarize deal descriptions
- Extract product attributes from unstructured text
- Personalize recommendations based on user preferences

**Trade-offs**:
- ✅ Lower cost and better rate limits
- ✅ Integrated billing and security
- ⚠️ AWS lock-in (mitigated by using standard inference API)
- ⚠️ Model selection limited to Bedrock offerings

---

### 10. DynamoDB + Aurora + S3 - Storage Layer

**Selected**: Multi-database strategy

#### DynamoDB (NoSQL)
**Use Cases**: Session state, deal cache (TTL), rate limiting counters

**Rationale**:
- **Performance**: Single-digit millisecond latency at any scale
- **TTL**: Automatic expiration for short-lived deal state (24-48 hours)
- **On-Demand Pricing**: Cost-effective for variable traffic
- **Streams**: Trigger Lambda functions on data changes

#### RDS Aurora PostgreSQL (Relational)
**Use Cases**: User accounts, deal history, analytics

**Rationale**:
- **ACID Transactions**: Critical for user accounts and billing
- **SQL**: Complex queries for analytics and reporting
- **Read Replicas**: Scale reads independently from writes
- **Compatibility**: Standard PostgreSQL (portable)

#### S3 (Object Storage)
**Use Cases**: Raw RSS feeds, model artifacts, backups, data lake

**Rationale**:
- **Durability**: 99.999999999% (11 9's) durability
- **Cost**: Cheapest storage option ($0.023/GB/month for Standard)
- **Lifecycle Policies**: Automatic transition to Glacier for archives
- **Versioning**: Protect against accidental deletion

**Why Multi-Database**:
Each database is optimized for its use case. Using a single database (e.g., only PostgreSQL) would sacrifice performance and cost-efficiency.

**Trade-offs**:
- ✅ Right tool for each job
- ✅ Cost and performance optimization
- ⚠️ Increased operational complexity (managed by using AWS managed services)

---

### 11. Terraform - Infrastructure as Code

**Selected**: Terraform

**Alternatives Considered**:
- AWS CloudFormation
- AWS CDK
- Pulumi

**Rationale**:
- **Multi-Cloud**: Can manage AWS, GCP, Azure from same codebase (future-proof)
- **Declarative**: Describe desired state, Terraform handles changes
- **State Management**: Remote state in S3 with locking (DynamoDB)
- **Modules**: Reusable components for consistency
- **Community**: Largest IaC community and module registry

**Why Terraform over CDK**:
- Language-agnostic (HCL is simpler than TypeScript/Python for infrastructure)
- Better for teams with mixed skill sets
- More portable across cloud providers
- Mature ecosystem and tooling

**Trade-offs**:
- ✅ Industry standard for IaC
- ✅ Portable across clouds
- ⚠️ HCL learning curve (but simpler than programming languages)
- ⚠️ State management requires discipline

---

### 12. Prometheus + Grafana - Monitoring

**Selected**: Prometheus + Grafana + CloudWatch

**Alternatives Considered**:
- CloudWatch alone
- DataDog (SaaS)
- New Relic (SaaS)
- Elastic Stack (ELK)

**Rationale**:
- **Open Source**: No per-metric pricing (CloudWatch charges per metric)
- **Flexible Queries**: PromQL is more powerful than CloudWatch Insights
- **Grafana Dashboards**: Best-in-class visualization
- **Alerting**: Powerful alert rules with Prometheus AlertManager
- **Portable**: Not locked to AWS

**Hybrid Approach**:
- **CloudWatch**: AWS service metrics (free tier covers basics)
- **Prometheus**: Custom application metrics, Kafka metrics
- **Grafana**: Unified dashboard for both CloudWatch and Prometheus

**Trade-offs**:
- ✅ Cost-effective at scale
- ✅ Powerful query language
- ⚠️ Requires running Prometheus server (use ECS Fargate)

---

## Decision Matrix

| Requirement | Technology | Primary Reason |
|-------------|-----------|----------------|
| Scalability | AWS + Auto-scaling | Handle variable traffic (10x peaks) |
| Real-time Delivery | Kafka + WebSocket | Sub-30s notification SLA |
| Cost Optimization | Spot instances, serverless | 50-70% cost reduction |
| Developer Velocity | Python + FastAPI | Single language, strong typing |
| Reliability | Multi-AZ, DLQ, retries | 99.9% uptime SLA |
| ML Integration | SageMaker + Bedrock | Managed model serving |
| Observability | Grafana + X-Ray | Full-stack tracing |
| Portability | Apache stack + Terraform | Avoid vendor lock-in |

---

## Cost Projection

**Estimated Monthly Costs** (1000 deals/hour, 10K users):

| Service | Monthly Cost | Justification |
|---------|-------------|---------------|
| AWS Lambda | $150-250 | Pay-per-execution for agents |
| ECS Fargate | $200-300 | API backend (2-4 tasks) |
| AWS MSK (Kafka) | $400-600 | 3-broker cluster, multi-AZ |
| OpenSearch | $300-500 | 3 data nodes + 3 master nodes |
| RDS Aurora | $150-250 | db.r6g.large with read replica |
| DynamoDB | $50-100 | On-demand pricing |
| S3 + CloudFront | $100-150 | Storage + CDN |
| AWS Bedrock | $200-400 | Claude API calls for notifications |
| EMR (Spot) | $100-200 | Batch processing (nightly) |
| Other (SNS, SQS, etc.) | $100-150 | Various services |
| **Total** | **$1,750-2,900** | Production-ready system |

**Cost Optimization Strategies**:
- Reserved Instances for baseline (30% savings)
- Spot Instances for EMR (70-90% savings)
- S3 Lifecycle → Glacier (80% storage cost reduction)
- Lambda vs. ECS analysis (use Lambda for <20% utilization)

---

## Future Considerations

### Technologies to Evaluate Later

1. **Apache Flink** (Stream Processing)
   - More powerful than Kafka Streams for complex event processing
   - Consider when adding real-time aggregations or windowing

2. **gRPC** (Inter-service Communication)
   - Replace REST for service-to-service calls if latency becomes critical
   - Better performance and type safety than JSON over HTTP

3. **Kubernetes (EKS)** (Container Orchestration)
   - Consider when moving beyond Lambda/ECS and need more control
   - Adds operational complexity but provides flexibility

4. **Redis for AI** (Vector Database)
   - Evaluate when Redis 7.2 vector search matures
   - May replace OpenSearch if Redis provides better performance/cost

---

## Lessons from Prototype

The prototype used **Gradio + OpenAI + ChromaDB** which was excellent for validating the concept but had limitations:

| Prototype Technology | Limitation | Production Solution |
|---------------------|-----------|-------------------|
| Gradio UI | Not production-ready | React.js + TypeScript |
| OpenAI API | Rate limits, cost | AWS Bedrock (Claude) |
| ChromaDB | Single-node, no HA | AWS OpenSearch |
| Synchronous execution | Slow, blocking | Step Functions + Lambda |
| Local file storage | Not scalable | S3 + DynamoDB + Aurora |
| No monitoring | Blind to issues | Prometheus + Grafana |

---

## Conclusion

The Deal Finder technology stack balances **managed services** (reducing operational overhead) with **open-source technologies** (avoiding vendor lock-in). Every technology selection optimizes for:

1. **Scalability**: Handle 10x traffic spikes without manual intervention
2. **Reliability**: 99.9% uptime with multi-AZ deployments
3. **Cost**: Optimize for variable workloads with auto-scaling and spot instances
4. **Developer Experience**: Modern tools with strong typing and excellent documentation
5. **Portability**: Use open standards (Kafka, Postgres, Terraform) where possible

This architecture is production-ready, cost-effective, and positions the system to scale from MVP to millions of users.
