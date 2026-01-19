# Deal Finder - Production Architecture Plan

**Project**: AI-Powered Deal Hunting Autonomous Agent System  
**Date**: January 19, 2026  
**Objective**: Transform educational prototype into production-ready system using AWS and Apache technologies

---

## Executive Summary

This plan outlines the transformation of "Deal Finder" - an AI agent framework that discovers online deals - from a Jupyter notebook prototype into a scalable, production-ready system deployed on AWS infrastructure with Apache technologies for data processing and streaming.

**Current System**: Single-instance Python application with:
- Gradio web UI
- OpenAI API integrations (GPT-5.1, GPT-5-mini)
- ChromaDB vector store (local persistence)
- RSS feed scraping
- Multi-agent orchestration
- Push notifications (Pushover API)

**Target Production System**: Cloud-native, microservices architecture with:
- High availability and auto-scaling
- Real-time streaming data pipeline
- Distributed vector database
- API-first design
- Comprehensive monitoring and observability
- CI/CD pipeline
- Multi-tenant support

---

## Architecture Overview

### High-Level Components

1. **Web Application Layer** (AWS ECS/Fargate)
2. **API Gateway Layer** (AWS API Gateway + Apache APISIX)
3. **Agent Orchestration Layer** (AWS Lambda + Step Functions)
4. **Data Streaming Layer** (Apache Kafka on AWS MSK)
5. **Vector Database Layer** (AWS OpenSearch Service with vector engine)
6. **Model Serving Layer** (AWS SageMaker + Bedrock)
7. **Data Processing Layer** (Apache Spark on AWS EMR)
8. **Storage Layer** (AWS S3 + DynamoDB + RDS Aurora)
9. **Messaging Layer** (AWS SNS/SQS)
10. **Monitoring & Observability** (AWS CloudWatch + Prometheus/Grafana)

---

## Component Details

### 1. Web Application Layer

**Current**: Gradio app running locally with threading for async updates

**Production Solution**:
- **Frontend**: React.js SPA deployed on AWS CloudFront + S3
  - Real-time updates via WebSocket (AWS API Gateway WebSocket)
  - Plotly.js for 3D vector visualization
  - Material-UI for modern interface
  
- **Backend API**: FastAPI/Flask containerized on AWS ECS Fargate
  - Auto-scaling group (2-10 instances)
  - Application Load Balancer (ALB)
  - Health checks and graceful shutdown
  - Session management via Redis (AWS ElastiCache)

**Implementation Steps**:
1. Rewrite Gradio UI as React components
2. Create REST API endpoints with FastAPI
3. Implement WebSocket handlers for real-time updates
4. Dockerize application
5. Create ECS task definitions and services
6. Configure ALB with target groups
7. Set up CloudFront distribution

### 2. API Gateway Layer

**Production Solution**:
- **AWS API Gateway**: Primary entry point
  - JWT authentication
  - Rate limiting and throttling
  - API versioning
  - Request/response transformation
  
- **Apache APISIX**: Advanced routing and service mesh
  - Dynamic upstream selection
  - Circuit breaker patterns
  - Request tracing
  - Plugin ecosystem for extensions

**Implementation Steps**:
1. Define OpenAPI 3.0 specification
2. Configure AWS API Gateway stages (dev, staging, prod)
3. Deploy Apache APISIX on EKS or ECS
4. Configure route rules and upstream services
5. Implement authentication middleware
6. Set up rate limiting policies

### 3. Agent Orchestration Layer

**Current**: Synchronous, single-threaded agent execution

**Production Solution**:
- **AWS Step Functions**: Orchestrate multi-agent workflow
  - State machine for deal discovery pipeline
  - Error handling and retry logic
  - Parallel execution of independent agents
  - Visual workflow monitoring
  
- **AWS Lambda Functions**: Individual agent implementations
  - `ScannerAgent`: RSS feed scraping (15-min timeout)
  - `EnsembleAgent`: Price estimation
  - `MessagingAgent`: Notification dispatch
  - `AutonomousPlanningAgent`: Orchestration controller

**Workflow Design**:
```
Start → Scan RSS Feeds → Filter New Deals → 
Parallel [
  Estimate Price (Specialist),
  Estimate Price (Frontier),
  Estimate Price (Neural Network)
] → Ensemble Weighting → Evaluate Discount → 
Decision (discount > threshold?) → 
  Yes: Send Notification → Update Memory
  No: Log and Skip
→ End
```

**Implementation Steps**:
1. Extract agent logic into standalone Lambda functions
2. Design Step Functions state machine (ASL JSON)
3. Configure Lambda layers for shared dependencies
4. Implement DynamoDB for state persistence
5. Add EventBridge rules for scheduled execution (every 5 minutes)
6. Configure dead letter queues (DLQ) for failed executions

### 4. Data Streaming Layer

**Production Solution**: **Apache Kafka on AWS MSK** (Managed Streaming for Kafka)

**Topics**:
- `deals.raw` - Raw RSS feed entries
- `deals.parsed` - Cleaned and structured deals
- `deals.evaluated` - Deals with price estimates
- `deals.opportunities` - High-discount deals
- `notifications.outbound` - Notifications to be sent
- `user.interactions` - User selections and feedback

**Stream Processing**:
- **Apache Kafka Streams** or **Apache Flink** on AWS Kinesis Data Analytics
- Real-time data enrichment
- Windowing for duplicate detection
- Join operations across topics

**Implementation Steps**:
1. Provision AWS MSK cluster (3 AZ, multi-broker)
2. Create Kafka topics with appropriate partitions
3. Implement Kafka producers in Scanner agent
4. Create Kafka consumers for downstream processing
5. Deploy Kafka Connect for data integration
6. Configure Schema Registry (AWS Glue Schema Registry)
7. Implement KSQL/Flink jobs for stream processing

### 5. Vector Database Layer

**Current**: ChromaDB with local persistence

**Production Solution**: **AWS OpenSearch Service with k-NN plugin**

**Features**:
- Distributed vector search at scale
- Multi-AZ deployment for high availability
- Approximate k-NN search (HNSW, IVF algorithms)
- Full-text search combined with vector similarity
- Index snapshots to S3

**Alternative**: **Pinecone** or **Weaviate** on AWS (managed vector DB)

**Implementation Steps**:
1. Provision OpenSearch domain (3 data nodes, 3 master nodes)
2. Create index with vector field mappings
3. Migrate existing ChromaDB data to OpenSearch
4. Implement vector embedding pipeline
5. Configure index refresh intervals
6. Set up automated snapshots to S3
7. Create search API endpoints

### 6. Model Serving Layer

**Current**: Direct OpenAI API calls, custom PyTorch models

**Production Solution**:

**For LLM Calls**:
- **AWS Bedrock**: Managed access to foundation models
  - Claude 3.5 Sonnet (replacing direct OpenAI calls)
  - Llama 3 for open-source alternative
  - Built-in rate limiting and cost management
  
**For Custom Models**:
- **AWS SageMaker**: Host fine-tuned pricing model
  - Real-time inference endpoint
  - Auto-scaling based on invocation rate
  - A/B testing for model versions
  - Model monitoring and drift detection

**Implementation Steps**:
1. Migrate OpenAI calls to AWS Bedrock SDK
2. Export PyTorch neural network model
3. Create SageMaker inference container
4. Deploy model endpoint with auto-scaling
5. Implement model versioning strategy
6. Set up SageMaker Model Monitor
7. Create fallback logic for model failures

### 7. Data Processing Layer

**Production Solution**: **Apache Spark on AWS EMR** (Elastic MapReduce)

**Use Cases**:
- Batch processing of historical deals (nightly)
- Feature engineering for ML models
- Data quality checks and validation
- Aggregated analytics and reporting
- Model training pipelines

**Jobs**:
- **Deal Enrichment**: Join deals with product catalog
- **Price Trend Analysis**: Calculate price history and trends
- **Model Retraining**: Periodic update of neural network weights
- **Data Cleanup**: Remove duplicates and expired deals

**Implementation Steps**:
1. Provision EMR cluster with Spark 3.5+
2. Create PySpark jobs for data processing
3. Configure AWS Glue Data Catalog for metadata
4. Implement job orchestration with Apache Airflow (MWAA)
5. Set up S3 as data lake for raw/processed data
6. Configure cluster auto-scaling
7. Implement job monitoring and alerting

### 8. Storage Layer

**Production Solution**:

**Relational Data** - **AWS RDS Aurora PostgreSQL**:
- User accounts and preferences
- Deal metadata and history
- Notification logs
- System configuration

**NoSQL Data** - **AWS DynamoDB**:
- Real-time deal state (TTL enabled)
- User sessions
- Agent execution state
- Rate limiting counters

**Object Storage** - **AWS S3**:
- Raw RSS feed archives
- Model artifacts and checkpoints
- Backup and disaster recovery
- Static web assets

**Caching** - **AWS ElastiCache (Redis)**:
- API response caching
- Session store
- Rate limiting distributed cache
- Real-time leaderboard (sorted sets)

**Implementation Steps**:
1. Design database schemas (Aurora)
2. Create DynamoDB tables with appropriate indexes
3. Set up S3 buckets with lifecycle policies
4. Configure Aurora read replicas for scaling
5. Implement database migration scripts (Flyway/Alembic)
6. Set up ElastiCache cluster
7. Implement connection pooling (PgBouncer)

### 9. Messaging Layer

**Production Solution**:

**Internal Messaging**:
- **AWS SQS**: Decoupled task queues
  - Deal processing queue
  - Notification queue
  - Dead letter queues
  
- **AWS SNS**: Pub/sub for events
  - Deal discovered events
  - System alerts
  - User notifications

**External Notifications**:
- **AWS SNS** → Multiple channels:
  - Email (AWS SES)
  - SMS (AWS SNS SMS)
  - Push notifications (AWS SNS Mobile Push)
  - Webhook integrations
- Maintain Pushover integration as plugin

**Implementation Steps**:
1. Create SQS queues with appropriate visibility timeout
2. Set up SNS topics and subscriptions
3. Implement SQS consumers with Lambda
4. Configure DLQ and retry policies
5. Create notification preference management
6. Implement circuit breaker for external APIs
7. Add notification templates and personalization

### 10. Monitoring & Observability

**Production Solution**:

**Metrics** - **AWS CloudWatch + Prometheus**:
- Application metrics (latency, throughput, errors)
- Infrastructure metrics (CPU, memory, network)
- Business metrics (deals discovered, notifications sent)
- Custom agent performance metrics

**Logs** - **AWS CloudWatch Logs + Apache Kafka**:
- Centralized log aggregation
- Structured logging (JSON format)
- Log retention policies
- Real-time log streaming to Kafka

**Tracing** - **AWS X-Ray + Jaeger**:
- Distributed tracing across microservices
- Agent execution flow visualization
- Performance bottleneck identification
- Dependency mapping

**Dashboards** - **Grafana + AWS CloudWatch Dashboards**:
- Real-time system health
- Agent performance metrics
- Business KPIs
- Cost monitoring

**Alerting** - **PagerDuty + AWS SNS**:
- On-call rotation
- Incident escalation
- Alert aggregation and deduplication

**Implementation Steps**:
1. Instrument code with OpenTelemetry SDK
2. Configure CloudWatch Log Groups
3. Deploy Prometheus on EKS
4. Set up Grafana dashboards
5. Create alerting rules and runbooks
6. Configure PagerDuty integration
7. Implement synthetic monitoring (AWS CloudWatch Synthetics)

---

## Security Architecture

### Authentication & Authorization
- **AWS Cognito**: User authentication and user pools
- **OAuth 2.0 / OIDC**: Third-party integration
- **IAM Roles**: Service-to-service authentication
- **API Keys**: External integrations

### Secrets Management
- **AWS Secrets Manager**: API keys and credentials
- **AWS Systems Manager Parameter Store**: Configuration
- Automatic rotation for database credentials

### Network Security
- **VPC**: Private subnets for backend services
- **Security Groups**: Fine-grained access control
- **NACLs**: Network-level filtering
- **AWS WAF**: Web application firewall
- **AWS Shield**: DDoS protection

### Data Security
- **Encryption at Rest**: S3/EBS encryption with KMS
- **Encryption in Transit**: TLS 1.3 everywhere
- **Data Masking**: PII protection in logs
- **Audit Logging**: AWS CloudTrail enabled

### Compliance
- GDPR compliance for user data
- SOC 2 controls
- Data retention policies
- Right to deletion implementation

**Implementation Steps**:
1. Design IAM roles and policies
2. Configure Cognito user pool
3. Enable CloudTrail for all services
4. Implement API Gateway authorizers
5. Configure AWS WAF rules
6. Enable GuardDuty for threat detection
7. Conduct security audit and penetration testing

---

## CI/CD Pipeline

### Source Control
- **GitHub**: Code repository
- Branch protection rules
- Required code reviews
- Automated code scanning (Dependabot, Snyk)

### Build Pipeline
- **AWS CodeBuild** or **GitHub Actions**
  - Automated testing (pytest, unittest)
  - Code quality checks (pylint, black, mypy)
  - Security scanning (bandit, safety)
  - Docker image building
  - Push to AWS ECR

### Deployment Pipeline
- **AWS CodePipeline** or **ArgoCD**
  - Multi-stage deployments (dev → staging → prod)
  - Approval gates for production
  - Blue-green deployments
  - Canary releases
  - Automated rollback on failures

### Infrastructure as Code
- **Terraform** or **AWS CDK**
  - Version-controlled infrastructure
  - Environment parity
  - Automated provisioning
  - State management in S3

**Implementation Steps**:
1. Create GitHub repository structure
2. Define Terraform modules for each component
3. Set up CodeBuild projects
4. Create CodePipeline definitions
5. Implement integration test suite
6. Configure deployment strategies
7. Create disaster recovery procedures

---

## Cost Optimization

### Strategies
1. **Right-sizing**: Use appropriate instance types
2. **Auto-scaling**: Scale based on demand
3. **Reserved Instances**: 1-year commitments for baseline
4. **Spot Instances**: For EMR and batch processing
5. **S3 Lifecycle Policies**: Move old data to Glacier
6. **Lambda Provisioned Concurrency**: Only for critical paths
7. **CloudFront Caching**: Reduce origin requests
8. **DynamoDB On-Demand**: For variable traffic patterns

### Monitoring
- AWS Cost Explorer dashboards
- Budgets and alerts
- Cost allocation tags
- Regular cost optimization reviews

**Estimated Monthly Costs** (moderate usage):
- Compute (ECS/Lambda): $300-500
- Storage (S3/RDS/DynamoDB): $200-400
- Networking (Data Transfer): $100-200
- MSK (Kafka): $400-600
- OpenSearch: $300-500
- Other Services: $200-300
**Total**: ~$1,500-2,500/month

---

## Migration Strategy

### Phase 1: Infrastructure Setup (Weeks 1-2)
- Provision AWS accounts and organization
- Set up VPC and networking
- Deploy development environment
- Configure CI/CD pipeline
- Establish monitoring baseline

### Phase 2: Data Layer Migration (Weeks 3-4)
- Migrate ChromaDB to OpenSearch
- Set up RDS Aurora database
- Create DynamoDB tables
- Configure S3 buckets
- Test data access patterns

### Phase 3: Application Refactoring (Weeks 5-8)
- Extract agents into Lambda functions
- Build FastAPI backend
- Develop React frontend
- Implement WebSocket handlers
- Create Step Functions workflow

### Phase 4: Streaming Infrastructure (Weeks 9-10)
- Deploy MSK cluster
- Implement Kafka producers/consumers
- Create stream processing jobs
- Integrate with existing agents

### Phase 5: Model Deployment (Weeks 11-12)
- Migrate to AWS Bedrock
- Deploy custom models to SageMaker
- Implement A/B testing framework
- Performance testing and optimization

### Phase 6: Testing & Validation (Weeks 13-14)
- Integration testing
- Load testing (Apache JMeter)
- Security testing
- User acceptance testing

### Phase 7: Production Deployment (Weeks 15-16)
- Blue-green deployment to production
- Gradual traffic migration
- Monitor and optimize
- Post-deployment validation

### Phase 8: Optimization & Documentation (Weeks 17-18)
- Performance tuning
- Cost optimization
- Documentation completion
- Team training

---

## Success Metrics

### Technical KPIs
- **Availability**: 99.9% uptime SLA
- **Latency**: P95 API response < 500ms
- **Throughput**: Handle 1000 deals/hour
- **Error Rate**: < 0.1% of requests
- **Recovery Time**: < 5 minutes MTTR

### Business KPIs
- **Deal Discovery Rate**: 50-100 new deals/day
- **Notification Accuracy**: > 90% relevant deals
- **User Engagement**: > 30% click-through rate
- **Cost per Notification**: < $0.10
- **User Satisfaction**: > 4.5/5 rating

---

## Risk Assessment

### High-Risk Items
1. **OpenAI API Costs**: Implement rate limiting and caching
2. **Vector DB Migration**: Test thoroughly before cutover
3. **Real-time Requirements**: Ensure WebSocket stability
4. **Third-party API Dependencies**: Circuit breakers and fallbacks

### Mitigation Strategies
- Comprehensive testing at each phase
- Feature flags for gradual rollout
- Rollback procedures documented
- Regular backup and disaster recovery drills
- Chaos engineering practices

---

## Future Enhancements

### Short-term (6 months)
- Mobile applications (iOS/Android)
- Browser extension
- Email digest feature
- Deal comparison tools

### Medium-term (12 months)
- Machine learning personalization
- Multi-marketplace support (Amazon, eBay, Walmart)
- Price trend predictions
- Community deal sharing

### Long-term (18+ months)
- Cryptocurrency deals support
- International marketplace expansion
- White-label solution for partners
- API marketplace for third-party integrations

---

## Appendices

### A. Technology Stack Summary
- **Frontend**: React.js, TypeScript, Material-UI
- **Backend**: Python 3.12, FastAPI, Pydantic
- **Data Streaming**: Apache Kafka (AWS MSK)
- **Data Processing**: Apache Spark (AWS EMR)
- **Vector DB**: AWS OpenSearch with k-NN
- **Relational DB**: AWS RDS Aurora PostgreSQL
- **NoSQL DB**: AWS DynamoDB
- **Caching**: Redis (AWS ElastiCache)
- **Object Storage**: AWS S3
- **Compute**: AWS Lambda, ECS Fargate
- **Orchestration**: AWS Step Functions
- **API Gateway**: AWS API Gateway, Apache APISIX
- **Monitoring**: CloudWatch, Prometheus, Grafana, X-Ray
- **IaC**: Terraform / AWS CDK
- **CI/CD**: GitHub Actions, AWS CodePipeline

### B. Team Requirements
- **Backend Engineers**: 2-3
- **Frontend Engineer**: 1-2
- **DevOps/SRE**: 1-2
- **ML Engineer**: 1
- **QA Engineer**: 1
- **Product Manager**: 1

### C. References
- AWS Well-Architected Framework
- Apache Kafka Best Practices
- OpenSearch Performance Tuning Guide
- FastAPI Documentation
- React.js Production Guidelines
