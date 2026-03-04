terraform {
  required_version = ">= 1.14"

  backend "s3" {
    bucket         = "dealfinder-terraform-state-dev"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "dealfinder-terraform-locks"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Networking Module
module "networking" {
  source = "../../modules/networking"

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_cidr           = var.vpc_cidr
  enable_nat_gateway = var.enable_nat_gateway

  tags = local.common_tags
}

# S3 Storage Module
module "s3" {
  source = "../../modules/data/s3"

  project_name = var.project_name
  environment  = var.environment

  tags = local.common_tags
}

# DynamoDB Module
module "dynamodb" {
  source = "../../modules/data/dynamodb"

  project_name = var.project_name
  environment  = var.environment

  tags = local.common_tags
}

# CloudWatch Monitoring Module
module "cloudwatch" {
  source = "../../modules/monitoring/cloudwatch"

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  log_retention_days = var.log_retention_days
  alarm_email        = var.alarm_email

  tags = local.common_tags
}

# Aurora PostgreSQL Module (Phase 2)
module "aurora" {
  source = "../../modules/data/aurora"
  count  = var.enable_aurora ? 1 : 0

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.networking.vpc_id
  vpc_cidr           = module.networking.vpc_cidr
  private_subnet_ids = module.networking.private_subnet_ids
  availability_zones = module.networking.availability_zones

  # Database configuration
  database_name   = var.aurora_database_name
  master_username = var.aurora_master_username
  master_password = var.aurora_master_password

  # Serverless v2 scaling
  min_capacity   = var.aurora_min_capacity
  max_capacity   = var.aurora_max_capacity
  instance_count = var.aurora_instance_count

  # Cost optimization for dev
  deletion_protection         = false
  enable_performance_insights = false
  monitoring_interval         = 0

  # Alarms
  create_cloudwatch_alarms = true
  alarm_sns_topic_arn      = module.cloudwatch.alarms_topic_arn

  tags = local.common_tags
}

# OpenSearch Module (Phase 2)
module "opensearch" {
  source = "../../modules/data/opensearch"
  count  = var.enable_opensearch ? 1 : 0

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.networking.vpc_id
  vpc_cidr           = module.networking.vpc_cidr
  private_subnet_ids = module.networking.private_subnet_ids

  # Cluster configuration (cost-optimized for dev)
  instance_type            = var.opensearch_instance_type
  instance_count           = var.opensearch_instance_count
  dedicated_master_enabled = var.opensearch_dedicated_master_enabled
  zone_awareness_enabled   = var.opensearch_zone_awareness_enabled
  ebs_volume_size          = var.opensearch_ebs_volume_size

  # Security
  enable_fine_grained_access = true
  master_user_name           = var.opensearch_master_user_name
  master_user_password       = var.opensearch_master_user_password

  # Snapshots
  create_snapshot_bucket = true

  # Service-linked role (set to false if already exists)
  create_service_linked_role = var.opensearch_create_service_linked_role

  # Alarms
  create_cloudwatch_alarms = true
  alarm_sns_topic_arn      = module.cloudwatch.alarms_topic_arn

  tags = local.common_tags
}

# Pipeline Module (Phase 3)
module "pipeline" {
  source = "../../modules/pipeline"

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids

  log_retention_days  = var.log_retention_days
  alarm_sns_topic_arn = module.cloudwatch.alarms_topic_arn

  enable_schedule     = var.enable_pipeline_schedule
  schedule_expression = var.pipeline_schedule_expression

  tags = local.common_tags
}
