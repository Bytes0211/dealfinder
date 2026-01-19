# Terraform Best Practices Guide - Deal Finder

## Table of Contents
- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Best Practices](#best-practices)
- [Cost Management](#cost-management)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)
- [Security Guidelines](#security-guidelines)

---

## Quick Start

### Prerequisites
1. **Terraform** v1.14+ installed
2. **AWS CLI** configured with valid credentials
3. **AWS Account** with appropriate IAM permissions

### Initial Setup

```bash
# Navigate to infrastructure directory
cd infrastructure

# Run bootstrap script to create S3 backend
./bootstrap.sh us-east-1 dev

# Navigate to dev environment
cd environments/dev

# Copy example variables file
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your configuration
vim terraform.tfvars

# Initialize Terraform
terraform init

# Review the execution plan
terraform plan

# Apply infrastructure (start with minimal resources)
terraform apply
```

---

## Architecture Overview

### Directory Structure

```
infrastructure/
├── bootstrap.sh                    # Backend setup script
├── environments/
│   ├── dev/                       # Development environment
│   │   ├── main.tf               # Main configuration
│   │   ├── variables.tf          # Input variables
│   │   ├── outputs.tf            # Output values
│   │   └── terraform.tfvars      # Variable values (gitignored)
│   ├── staging/                   # Staging environment
│   └── prod/                      # Production environment
├── modules/
│   ├── networking/                # VPC, subnets, routing
│   ├── compute/
│   │   ├── ecs/                  # Fargate tasks
│   │   ├── lambda/               # Lambda functions
│   │   └── step-functions/       # Step Functions workflows
│   ├── data/
│   │   ├── aurora/               # RDS Aurora (persistent)
│   │   ├── dynamodb/             # DynamoDB tables
│   │   ├── s3/                   # S3 buckets
│   │   ├── opensearch/           # OpenSearch (destroyable)
│   │   ├── msk/                  # Kafka (destroyable)
│   │   └── emr/                  # Spark (destroyable)
│   ├── ml/
│   │   ├── sagemaker/            # Model endpoints
│   │   └── bedrock/              # LLM configuration
│   ├── monitoring/                # CloudWatch, Prometheus
│   └── security/                  # IAM, Secrets Manager
└── shared/
    ├── providers.tf              # Provider configuration
    ├── variables.tf              # Common variables
    └── outputs.tf                # Common outputs
```

### Module Organization Philosophy

- **Persistent Modules**: VPC, S3, DynamoDB, Aurora (tagged `Persistent=true`)
- **Destroyable Modules**: MSK, OpenSearch, EMR, ECS (tagged `Persistent=false`)
- **Feature Flags**: Use `enable_*` variables to control expensive resources

---

## Best Practices

### 1. State Management

**Always use remote state with locking:**

```hcl
terraform {
  backend "s3" {
    bucket         = "dealfinder-terraform-state-dev"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "dealfinder-terraform-locks"
  }
}
```

**State best practices:**
- ✅ Use separate state files per environment
- ✅ Enable versioning on S3 state bucket
- ✅ Enable encryption at rest
- ✅ Use DynamoDB for state locking
- ❌ Never commit `.tfstate` files to Git
- ❌ Never manually edit state files

### 2. Variable Management

**Use `.tfvars` files for environment-specific values:**

```hcl
# terraform.tfvars (gitignored)
aws_region     = "us-east-1"
enable_msk     = true   # Only when actively developing
enable_opensearch = false
```

**Variable validation:**

```hcl
variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}
```

### 3. Resource Tagging

**All resources must have consistent tags:**

```hcl
tags = merge(
  var.tags,
  {
    Name       = "${var.project_name}-${var.environment}-resource-name"
    Project    = var.project_name
    Environment = var.environment
    ManagedBy  = "terraform"
    Persistent = "true" # or "false"
  }
)
```

**Tag strategy:**
- `Project`: Always "dealfinder"
- `Environment`: dev/staging/prod
- `ManagedBy`: Always "terraform"
- `Persistent`: "true" for data resources, "false" for compute
- `CostCenter`: For cost allocation
- `Owner`: Team or individual responsible

### 4. Module Design

**Create reusable, composable modules:**

```hcl
module "networking" {
  source = "../../modules/networking"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  enable_nat_gateway = var.enable_nat_gateway

  tags = local.common_tags
}
```

**Module best practices:**
- ✅ One responsibility per module
- ✅ Expose outputs for module chaining
- ✅ Use variables for all configuration
- ✅ Document inputs and outputs
- ❌ Avoid hardcoded values
- ❌ Don't nest modules more than 2 levels

### 5. Resource Lifecycle Management

**Protect critical resources from accidental deletion:**

```hcl
resource "aws_db_instance" "aurora" {
  # ... configuration ...

  final_snapshot_identifier = "dealfinder-${var.environment}-final-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  skip_final_snapshot       = false
  deletion_protection       = var.environment == "prod" ? true : false

  lifecycle {
    prevent_destroy = var.environment == "prod" ? true : false
  }
}
```

### 6. Security Best Practices

**Never hardcode credentials:**

```hcl
# ❌ BAD
resource "aws_db_instance" "example" {
  username = "admin"
  password = "supersecret123"
}

# ✅ GOOD
resource "aws_db_instance" "example" {
  username = var.db_username
  password = data.aws_secretsmanager_secret_version.db_password.secret_string
}
```

**Use AWS Secrets Manager:**

```hcl
data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = "${var.project_name}-${var.environment}-db-password"
}
```

### 7. Dependency Management

**Use explicit dependencies when needed:**

```hcl
resource "aws_nat_gateway" "main" {
  # ... configuration ...
  depends_on = [aws_internet_gateway.main]
}
```

**Implicit dependencies are preferred:**

```hcl
resource "aws_route" "private_nat" {
  route_table_id = aws_route_table.private.id
  nat_gateway_id = aws_nat_gateway.main.id  # Implicit dependency
}
```

### 8. Output Values

**Expose useful information for other modules:**

```hcl
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = aws_subnet.private[*].id
}
```

### 9. Code Formatting

**Always format your code:**

```bash
terraform fmt -recursive
```

**Validation:**

```bash
terraform validate
```

### 10. Documentation

**Document complex logic and decisions:**

```hcl
# Use Spot instances for EMR to save 70-90% on compute costs
# Suitable for non-critical batch processing workloads
resource "aws_emr_instance_fleet" "core" {
  instance_type_configs {
    instance_type     = "r5.xlarge"
    weighted_capacity = 1
    bid_price_as_percentage_of_on_demand_price = 100
  }
}
```

---

## Cost Management

### Cost-Saving Strategies

#### 1. Feature Flags for Expensive Resources

**Use variables to enable/disable costly infrastructure:**

```hcl
variable "enable_msk" {
  description = "Enable MSK Kafka cluster (saves ~$400-600/month when disabled)"
  type        = bool
  default     = false
}

resource "aws_msk_cluster" "kafka" {
  count = var.enable_msk ? 1 : 0
  # ... configuration ...
}
```

#### 2. Targeted Resource Destruction

**Destroy specific expensive resources while keeping data:**

```bash
# Destroy MSK cluster
terraform destroy -target=module.msk

# Destroy OpenSearch
terraform destroy -target=module.opensearch

# Destroy ECS tasks
terraform destroy -target=module.ecs

# Keep: VPC, S3, DynamoDB, Aurora
```

#### 3. Daily Development Pattern

**Morning (start development):**

```bash
# Enable only what you need
terraform apply -target=module.networking
terraform apply -target=module.lambda
terraform apply -target=module.msk  # Only if working on streaming
```

**Evening (save costs):**

```bash
# Destroy expensive compute resources
terraform destroy -target=module.msk
terraform destroy -target=module.opensearch
terraform destroy -target=module.ecs
```

#### 4. Weekend/Idle Shutdown

**Friday evening:**

```bash
# Destroy all non-persistent infrastructure
terraform destroy -target=module.compute
terraform destroy -target=module.streaming
terraform destroy -target=module.monitoring

# Keep running: S3, DynamoDB, Aurora (snapshot to smaller instance)
```

**Monday morning:**

```bash
terraform apply  # Restore infrastructure
```

#### 5. Cost Monitoring

**Set up AWS Budgets:**

```bash
aws budgets create-budget \
  --account-id <your-account-id> \
  --budget file://budget.json \
  --notifications-with-subscribers file://notifications.json
```

**Query costs by tag:**

```bash
aws ce get-cost-and-usage \
  --time-period Start=2026-01-01,End=2026-01-31 \
  --granularity MONTHLY \
  --metrics "BlendedCost" \
  --group-by Type=TAG,Key=Environment
```

### Monthly Cost Breakdown

| Component | Monthly Cost | Persistent | Notes |
|-----------|--------------|------------|-------|
| **VPC** | $0 | Yes | Free tier |
| **NAT Gateway** | $100-150 | No | Destroyable, disable in dev |
| **S3** | $50-100 | Yes | Minimal when not in use |
| **DynamoDB** | $50-100 | Yes | On-demand, scales to zero |
| **Aurora** | $150-250 | Yes | Use t4g.medium in dev |
| **MSK (Kafka)** | $400-600 | No | **Destroy when not in use** |
| **OpenSearch** | $300-500 | No | **Destroy when not in use** |
| **EMR** | $100-200 | No | Use Spot instances |
| **ECS Fargate** | $200-300 | No | **Destroy when not in use** |
| **Lambda** | $50-150 | No | Pay per invocation |
| **SageMaker** | $100-300 | No | Destroy endpoints when not testing |

**Total (all enabled)**: ~$1,500-2,500/month  
**Total (persistent only)**: ~$250-450/month (83% savings)

---

## Common Workflows

### 1. First-Time Setup

```bash
# 1. Bootstrap backend
cd infrastructure
./bootstrap.sh us-east-1 dev

# 2. Configure environment
cd environments/dev
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars

# 3. Initialize and plan
terraform init
terraform plan

# 4. Apply minimal infrastructure
terraform apply
```

### 2. Adding New Resources

```bash
# 1. Edit main.tf to add module or resource
vim main.tf

# 2. Format and validate
terraform fmt
terraform validate

# 3. Plan changes
terraform plan -out=tfplan

# 4. Review plan carefully
# 5. Apply changes
terraform apply tfplan
```

### 3. Destroying Specific Resources

```bash
# Target specific modules
terraform destroy -target=module.msk
terraform destroy -target=module.opensearch

# Or use feature flags
terraform apply -var="enable_msk=false"
```

### 4. Switching Environments

```bash
# Development
cd environments/dev
terraform init
terraform apply

# Staging
cd ../staging
terraform init
terraform apply

# Production (requires approval)
cd ../prod
terraform init
terraform plan
# Review carefully
terraform apply
```

### 5. Updating Modules

```bash
# After modifying a module
terraform get -update
terraform plan
terraform apply
```

### 6. Importing Existing Resources

```bash
# Import manually created resources into Terraform state
terraform import module.s3.aws_s3_bucket.data_lake dealfinder-dev-data-lake

# Verify import
terraform plan  # Should show no changes
```

### 7. State Management

```bash
# List resources in state
terraform state list

# Show specific resource
terraform state show module.networking.aws_vpc.main

# Move resource in state (refactoring)
terraform state mv \
  aws_instance.example \
  module.compute.aws_instance.example

# Remove resource from state (without destroying)
terraform state rm module.old_module
```

### 8. Disaster Recovery

```bash
# 1. Backup current state
aws s3 cp \
  s3://dealfinder-terraform-state-dev/dev/terraform.tfstate \
  ./terraform.tfstate.backup

# 2. Restore from previous version (if needed)
aws s3api list-object-versions \
  --bucket dealfinder-terraform-state-dev \
  --prefix dev/terraform.tfstate

aws s3api get-object \
  --bucket dealfinder-terraform-state-dev \
  --key dev/terraform.tfstate \
  --version-id <version-id> \
  terraform.tfstate.restored
```

---

## Troubleshooting

### Common Issues

#### 1. State Lock Error

**Problem:**
```
Error: Error acquiring the state lock
Lock Info:
  ID:        abc123...
  Operation: OperationTypeApply
```

**Solution:**
```bash
# Check if another operation is running
# If stuck, force unlock (use with caution)
terraform force-unlock abc123
```

#### 2. Resource Already Exists

**Problem:**
```
Error: A resource with the ID "dealfinder-dev-vpc" already exists
```

**Solution:**
```bash
# Import existing resource
terraform import module.networking.aws_vpc.main vpc-abc123

# Or delete manually and recreate
aws ec2 delete-vpc --vpc-id vpc-abc123
terraform apply
```

#### 3. Backend Configuration Error

**Problem:**
```
Error: Failed to get existing workspaces: S3 bucket does not exist
```

**Solution:**
```bash
# Run bootstrap script
cd infrastructure
./bootstrap.sh us-east-1 dev
```

#### 4. Module Not Found

**Problem:**
```
Error: Module not installed
```

**Solution:**
```bash
terraform init
terraform get
```

#### 5. Insufficient IAM Permissions

**Problem:**
```
Error: UnauthorizedOperation: You are not authorized to perform this operation
```

**Solution:**
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check IAM permissions (requires appropriate policies)
# Add required IAM policies for Terraform operations
```

---

## Security Guidelines

### 1. Secrets Management

**Never commit secrets to Git:**

```bash
# .gitignore (already configured)
*.tfvars
*.tfstate
*.tfstate.*
.terraform/
```

**Use AWS Secrets Manager:**

```hcl
resource "aws_secretsmanager_secret" "db_password" {
  name = "${var.project_name}-${var.environment}-db-password"
}

data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_secretsmanager_secret.db_password.id
}
```

### 2. IAM Roles and Policies

**Use least privilege principle:**

```hcl
resource "aws_iam_role" "lambda_execution" {
  name = "${var.project_name}-${var.environment}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
```

### 3. Network Security

**Use private subnets for backends:**

```hcl
resource "aws_db_instance" "aurora" {
  db_subnet_group_name   = aws_db_subnet_group.private.name
  publicly_accessible    = false
  vpc_security_group_ids = [aws_security_group.database.id]
}
```

### 4. Encryption

**Enable encryption for all data stores:**

```hcl
resource "aws_s3_bucket_server_side_encryption_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_db_instance" "aurora" {
  storage_encrypted = true
  kms_key_id        = aws_kms_key.database.arn
}
```

### 5. Access Control

**Block public access to S3:**

```hcl
resource "aws_s3_bucket_public_access_block" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

---

## Additional Resources

### Official Documentation
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Terraform Best Practices](https://www.terraform-best-practices.com/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)

### Terraform Commands Reference

```bash
terraform init          # Initialize working directory
terraform plan          # Show execution plan
terraform apply         # Apply changes
terraform destroy       # Destroy infrastructure
terraform fmt           # Format code
terraform validate      # Validate configuration
terraform state list    # List resources in state
terraform output        # Show outputs
terraform graph         # Generate dependency graph
terraform console       # Interactive console
```

### Getting Help

```bash
terraform -help
terraform plan -help
terraform apply -help
```

---

## Appendix: Example .gitignore

```gitignore
# Terraform
.terraform/
.terraform.lock.hcl
*.tfstate
*.tfstate.*
*.tfvars
*.tfplan
crash.log
override.tf
override.tf.json
*_override.tf
*_override.tf.json

# Sensitive
*.pem
*.key
credentials.json
```

---

**Last Updated**: January 19, 2026  
**Version**: 1.0  
**Maintainer**: Deal Finder Team
