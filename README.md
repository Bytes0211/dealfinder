# Deal Finder

> AI-Powered Deal Hunting Autonomous Agent System

An intelligent multi-agent system that discovers online deals through RSS feeds, estimates prices using ensemble ML models, and delivers real-time notifications for high-value opportunities.

## 🎯 Project Status

**Current Phase**: Phase 2 Complete ✅ - Data Layer Implemented | Ready for Phase 3

**Infrastructure Live**: 47 AWS resources deployed (Phase 1) + Data layer modules ready (Phase 2).

This repository contains comprehensive architecture documentation and a cost-optimized, production-ready infrastructure foundation.

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
├── AGENTS.md                      # Warp AI agent guidance (WARP rules)
├── PRODUCTION_PLAN.md             # Complete production architecture plan
├── PROCESS_FLOWS.md               # Visual workflow diagrams
├── TECHNOLOGY_RATIONALE.md        # Technology selection reasoning
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                # CI pipeline (lint, test, security)
│   │   └── cd.yml                # CD pipeline (deploy infrastructure)
│   └── dependabot.yml            # Automated dependency updates
├── developer/
│   ├── developer_journal.md       # Development session logs
│   └── project-status.md          # Detailed project timeline and status
├── docs/
│   └── APACHE_ZEPPELIN.md         # Zeppelin documentation
├── infrastructure/                # Terraform IaC ✅ DEPLOYED
│   ├── bootstrap.sh              # Backend setup script
│   ├── environments/
│   │   └── dev/                  # Dev environment (live)
│   └── modules/
│       ├── networking/           # VPC, subnets, endpoints
│       ├── data/                 # S3, DynamoDB
│       └── monitoring/           # CloudWatch, alarms
├── src/                           # Source code
│   └── dealfinder/               # Python package structure
├── tests/                         # Test suite ✅ 97 TESTS PASSING
│   ├── unit/                     # Unit tests for configs
│   └── infrastructure/           # Infrastructure validation
├── socialmedia/                   # Social media content
└── scripts/                       # Utility scripts (TBD)
```

## 📚 Documentation

- **[developer/project-status.md](developer/project-status.md)**: Project timeline, phase breakdown, and current status
- **[PRODUCTION_PLAN.md](PRODUCTION_PLAN.md)**: Detailed system design, component specifications, and migration strategy
- **[PROCESS_FLOWS.md](PROCESS_FLOWS.md)**: Visual diagrams of data flows, pipelines, and workflows
- **[TECHNOLOGY_RATIONALE.md](TECHNOLOGY_RATIONALE.md)**: Reasoning behind each technology choice with alternatives considered
- **[AGENTS.md](AGENTS.md)**: Context for Warp AI agent when working in this repository
- **[infrastructure/README.md](infrastructure/README.md)**: Infrastructure deployment guide
- **[infrastructure/TERRAFORM_GUIDE.md](infrastructure/TERRAFORM_GUIDE.md)**: Terraform best practices and workflows
- **[docs/APACHE_ZEPPELIN.md](docs/APACHE_ZEPPELIN.md)**: Guide to Apache Zeppelin for interactive Spark development

## 🚀 Getting Started

### Prerequisites

- AWS Account with programmatic access
- Terraform 1.14+
- Python 3.12+
- uv package manager
- Git

### Development Setup

```bash
# Clone repository
git clone https://github.com/Bytes0211/dealfinder.git
cd dealfinder

# Install Python dependencies
uv pip install -e .

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
# Run all unit tests
pytest tests/unit/ -v

# Run infrastructure validation tests
pytest tests/infrastructure/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

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

### Phase 1: Infrastructure Setup (Weeks 1-2) ✅ COMPLETE
- [x] Provision AWS accounts and VPC
- [x] Set up CI/CD pipeline  
- [x] Deploy development environment
- [x] Implement monitoring and cost controls
- [x] Create comprehensive test suite (97 tests)

### Phase 2: Data Layer (Weeks 3-4) ✅ COMPLETE
- [x] Aurora PostgreSQL Serverless v2 Terraform module
- [x] OpenSearch with k-NN plugin Terraform module
- [x] SQLAlchemy ORM models (5 models, 3 enums)
- [x] Alembic migration framework
- [x] OpenSearch client with vector search
- [x] Repository pattern data access layer

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
