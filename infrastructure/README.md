# Deal Finder - Infrastructure

This directory contains Terraform infrastructure as code (IaC) for the Deal Finder project.

## Quick Start

### Prerequisites
- Terraform v1.14+ installed
- AWS CLI configured with valid credentials
- AWS account with appropriate permissions

### Initial Setup

```bash
# 1. Bootstrap Terraform backend (one-time setup)
./bootstrap.sh us-east-1 dev

# 2. Navigate to dev environment
cd environments/dev

# 3. Copy and configure variables
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars  # Edit with your configuration

# 4. Initialize Terraform
terraform init

# 5. Review plan
terraform plan

# 6. Apply infrastructure (start with minimal resources)
terraform apply
```

## Directory Structure

```
infrastructure/
├── bootstrap.sh              # Backend setup script
├── environments/
│   ├── dev/                 # Development environment
│   ├── staging/             # Staging environment
│   └── prod/                # Production environment
├── modules/
│   ├── networking/          # VPC, subnets, NAT Gateway
│   ├── compute/             # Lambda, ECS, Step Functions
│   ├── data/                # S3, DynamoDB, Aurora, OpenSearch, MSK
│   ├── ml/                  # SageMaker, Bedrock
│   ├── monitoring/          # CloudWatch, Prometheus, Grafana
│   └── security/            # IAM, Secrets Manager, Cognito
└── shared/                  # Common configuration
```

## Cost Management

### Feature Flags

All expensive resources are controlled by feature flags (disabled by default):

```hcl
enable_nat_gateway = false  # Save ~$100/month
enable_msk         = false  # Save ~$400-600/month
enable_opensearch  = false  # Save ~$300-500/month
enable_emr         = false  # Save ~$100-200/month
enable_ecs         = false  # Save ~$200-300/month
```

### Targeted Destruction

Destroy specific resources while keeping data:

```bash
# Destroy expensive resources
terraform destroy -target=module.msk
terraform destroy -target=module.opensearch
terraform destroy -target=module.ecs

# Persistent resources remain intact (S3, DynamoDB, VPC)
```

### Cost Breakdown

| Resource | Monthly Cost | Persistent | Can Destroy |
|----------|--------------|------------|-------------|
| VPC | $0 | Yes | No |
| NAT Gateway | $100-150 | No | Yes |
| S3 | $50-100 | Yes | No |
| DynamoDB | $50-100 | Yes | No |
| Aurora | $150-250 | Yes | Snapshot first |
| MSK | $400-600 | No | **Yes** |
| OpenSearch | $300-500 | No | **Yes** |
| EMR | $100-200 | No | **Yes** |
| ECS | $200-300 | No | **Yes** |
| Lambda | $50-150 | No | Auto-scales |

**Total (all enabled)**: ~$1,500-2,500/month  
**Total (persistent only)**: ~$250-450/month (83% savings)

## Implemented Modules

### ✅ Completed
- **networking**: VPC, subnets, NAT Gateway, VPC endpoints
- **data/s3**: Data lake, models, backups buckets
- **data/dynamodb**: Deal state, agent state, user sessions tables

### 🚧 In Progress
- **data/aurora**: RDS Aurora PostgreSQL (persistent data)
- **data/opensearch**: Vector database (destroyable)
- **data/msk**: Apache Kafka cluster (destroyable)
- **data/emr**: Spark batch processing (destroyable)
- **compute/lambda**: Agent functions
- **compute/ecs**: API backend (destroyable)
- **compute/step-functions**: Workflow orchestration
- **ml/sagemaker**: Model endpoints
- **ml/bedrock**: LLM configuration
- **monitoring/cloudwatch**: Metrics and logs
- **monitoring/prometheus**: Custom metrics
- **security/iam**: Roles and policies
- **security/secrets-manager**: Credentials management

## Daily Development Workflow

### Morning (Start Development)

```bash
cd environments/dev

# Enable only what you need
terraform apply -var="enable_msk=true"  # If working on streaming
terraform apply -var="enable_ecs=true"  # If working on API
```

### Evening (Save Costs)

```bash
# Destroy expensive resources
terraform destroy -target=module.msk
terraform destroy -target=module.opensearch
terraform destroy -target=module.ecs
```

### Weekend/Idle Periods

```bash
# Friday evening - destroy all non-persistent infrastructure
terraform destroy -target=module.compute
terraform destroy -target=module.streaming

# Monday morning - restore
terraform apply
```

## Documentation

- **[TERRAFORM_GUIDE.md](TERRAFORM_GUIDE.md)**: Comprehensive guide to Terraform best practices, workflows, and troubleshooting
- **[PRODUCTION_PLAN.md](../PRODUCTION_PLAN.md)**: Complete system architecture
- **[TECHNOLOGY_RATIONALE.md](../TECHNOLOGY_RATIONALE.md)**: Technology selection reasoning

## Common Commands

```bash
# Format code
terraform fmt -recursive

# Validate configuration
terraform validate

# Plan changes
terraform plan

# Apply changes
terraform apply

# Destroy specific resource
terraform destroy -target=module.msk

# Show outputs
terraform output

# List resources
terraform state list
```

## Security

- Never commit `.tfvars` files (gitignored)
- Never hardcode credentials in Terraform files
- Always use AWS Secrets Manager for sensitive data
- Enable encryption for all data at rest
- Use private subnets for backend services

## Support

For detailed guidance, see:
- [Terraform Guide](TERRAFORM_GUIDE.md) - Best practices and workflows
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Terraform AWS Provider Docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

---

**Version**: 1.0  
**Last Updated**: January 19, 2026
