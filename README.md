# Deal Finder

> AI-Powered Deal Hunting Autonomous Agent System

An intelligent multi-agent system that discovers online deals through RSS feeds, estimates prices using ensemble ML models, and delivers real-time notifications for high-value opportunities.

## 🎯 Project Status

**Current Phase**: Pre-implementation planning and architecture design

This repository contains comprehensive architecture documentation for transforming a Jupyter notebook prototype into a production-ready, cloud-native system.

## 🏗️ Architecture Overview

Deal Finder is a **multi-agent AI system** built on AWS with Apache technologies:

```
RSS Feeds → Scanner Agent → Kafka Streaming → Ensemble ML Models → Evaluation → Notifications
```

### Key Components

- **Agent Architecture**: Scanner, Ensemble, Messaging, and Autonomous Planning agents
- **Orchestration**: AWS Step Functions coordinating agent workflows
- **Streaming**: Apache Kafka (AWS MSK) for event-driven data flow
- **Vector DB**: AWS OpenSearch for similarity search and recommendations
- **Batch Processing**: Apache Spark (AWS EMR) for analytics and model training
- **Notifications**: Multi-channel delivery (Pushover, Email, SMS, WebSocket)

## 📊 System Capabilities

- **Real-time Deal Discovery**: Scan 1000+ deals/hour from RSS feeds
- **Ensemble Price Estimation**: Combine multiple ML models for accurate pricing
- **Smart Filtering**: Notify only when discount exceeds configurable threshold
- **Personalization**: AI-generated messages tailored to user preferences
- **High Availability**: 99.9% uptime with multi-AZ deployment

## 🛠️ Technology Stack

### Backend
- **Language**: Python 3.12
- **API Framework**: FastAPI with Pydantic
- **Orchestration**: AWS Lambda + Step Functions
- **Compute**: ECS Fargate, AWS Lambda

### Data Layer
- **Streaming**: Apache Kafka (AWS MSK)
- **Batch Processing**: Apache Spark (AWS EMR)
- **Vector Database**: AWS OpenSearch with k-NN plugin
- **Relational DB**: AWS RDS Aurora PostgreSQL
- **NoSQL**: AWS DynamoDB
- **Object Storage**: AWS S3

### ML & AI
- **LLM**: AWS Bedrock (Claude 3.5 Sonnet)
- **Model Serving**: AWS SageMaker
- **Model Types**: Specialist, Frontier, Neural Network ensemble

### Frontend
- **Framework**: React.js with TypeScript
- **UI Library**: Material-UI
- **Visualization**: Plotly.js
- **Real-time**: WebSocket for live updates

### Infrastructure
- **IaC**: Terraform
- **CI/CD**: GitHub Actions / AWS CodePipeline
- **Monitoring**: Prometheus, Grafana, CloudWatch, X-Ray
- **Secrets**: AWS Secrets Manager

## 📁 Repository Structure

```
dealfinder/
├── README.md                      # This file
├── WARP.md                        # Warp AI agent guidance
├── PRODUCTION_PLAN.md             # Complete production architecture plan
├── PROCESS_FLOWS.md               # Visual workflow diagrams
├── TECHNOLOGY_RATIONALE.md        # Technology selection reasoning
├── docs/
│   └── APACHE_ZEPPELIN.md         # Zeppelin documentation
├── src/                           # Source code (TBD)
│   ├── agents/                    # Agent implementations
│   ├── api/                       # FastAPI backend
│   ├── ml/                        # ML models
│   └── frontend/                  # React application
├── infrastructure/                # Terraform/IaC (TBD)
├── tests/                         # Test suite (TBD)
└── scripts/                       # Utility scripts (TBD)
```

## 📚 Documentation

- **[PRODUCTION_PLAN.md](PRODUCTION_PLAN.md)**: Detailed system design, component specifications, and migration strategy
- **[PROCESS_FLOWS.md](PROCESS_FLOWS.md)**: Visual diagrams of data flows, pipelines, and workflows
- **[TECHNOLOGY_RATIONALE.md](TECHNOLOGY_RATIONALE.md)**: Reasoning behind each technology choice with alternatives considered
- **[WARP.md](WARP.md)**: Context for Warp AI agent when working in this repository
- **[docs/APACHE_ZEPPELIN.md](docs/APACHE_ZEPPELIN.md)**: Guide to Apache Zeppelin for interactive Spark development

## 🚀 Getting Started

### Prerequisites

*To be added when implementation begins*

### Development Setup

*To be added when implementation begins*

### Running Tests

*To be added when implementation begins*

## 📈 Performance Targets

| Metric | Target | Purpose |
|--------|--------|---------|
| **API Latency** | < 500ms (P95) | Responsive user experience |
| **Notification Delivery** | < 30 seconds | Real-time alerts |
| **Throughput** | 1000 deals/hour | Scale for multiple RSS sources |
| **Availability** | 99.9% uptime | Reliable service |
| **Error Rate** | < 0.1% | High-quality notifications |

## 💰 Cost Estimation

**Estimated Monthly Costs** (1000 deals/hour, 10K users): **$1,750 - $2,900**

Major cost drivers:
- AWS MSK (Kafka): $400-600
- OpenSearch: $300-500
- ECS Fargate: $200-300
- RDS Aurora: $150-250
- AWS Bedrock: $200-400

See [TECHNOLOGY_RATIONALE.md](TECHNOLOGY_RATIONALE.md#cost-projection) for detailed breakdown.

## 🗺️ Roadmap

### Phase 1: Infrastructure Setup (Weeks 1-2)
- [ ] Provision AWS accounts and VPC
- [ ] Set up CI/CD pipeline
- [ ] Deploy development environment

### Phase 2: Data Layer (Weeks 3-4)
- [ ] Migrate ChromaDB to OpenSearch
- [ ] Set up RDS Aurora and DynamoDB
- [ ] Configure S3 data lake

### Phase 3: Application Development (Weeks 5-8)
- [ ] Implement Lambda agents
- [ ] Build FastAPI backend
- [ ] Develop React frontend
- [ ] Create Step Functions workflows

### Phase 4: Streaming Infrastructure (Weeks 9-10)
- [ ] Deploy MSK cluster
- [ ] Implement Kafka producers/consumers
- [ ] Create stream processing jobs

### Phase 5: Model Deployment (Weeks 11-12)
- [ ] Migrate to AWS Bedrock
- [ ] Deploy models to SageMaker
- [ ] Implement A/B testing

### Phase 6: Testing & Validation (Weeks 13-14)
- [ ] Integration testing
- [ ] Load testing
- [ ] Security testing

### Phase 7: Production Deployment (Weeks 15-16)
- [ ] Blue-green deployment
- [ ] Traffic migration
- [ ] Monitoring and optimization

### Phase 8: Documentation & Training (Weeks 17-18)
- [ ] Complete documentation
- [ ] Team training
- [ ] Runbooks and procedures

## 🔒 Security

- **Authentication**: AWS Cognito with OAuth 2.0
- **Authorization**: IAM roles for service-to-service
- **Secrets**: AWS Secrets Manager (never hardcoded)
- **Network**: Private VPC subnets for backend services
- **Encryption**: TLS 1.3 in transit, KMS at rest
- **Compliance**: GDPR-ready with data retention policies

## 🤝 Contributing

*To be added when project transitions to active development*

## 📄 License

*To be determined*

## 🔗 Related Projects

This system is being transformed from a Jupyter notebook prototype. Key migrations:

- **UI**: Gradio → React.js + TypeScript
- **LLM**: OpenAI API → AWS Bedrock (Claude)
- **Vector DB**: ChromaDB → AWS OpenSearch
- **Orchestration**: Synchronous → AWS Step Functions
- **Storage**: Local files → S3 + DynamoDB + Aurora

## 📞 Contact

*To be added*

---

**Built with** ☁️ AWS | 🔥 Apache Technologies | 🤖 AI/ML | ⚡ Event-Driven Architecture
