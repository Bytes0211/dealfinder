terraform {
  required_version = ">= 1.14"

  backend "s3" {
    bucket       = "dealfinder-terraform-state-prod"
    key          = "prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
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

# ── Networking ──────────────────────────────────────────────────────────────

module "networking" {
  source = "../../modules/networking"

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_cidr           = var.vpc_cidr
  enable_nat_gateway = var.enable_nat_gateway

  tags = local.common_tags
}

# ── Storage ─────────────────────────────────────────────────────────────────

module "s3" {
  source = "../../modules/data/s3"

  project_name = var.project_name
  environment  = var.environment

  tags = local.common_tags
}

module "dynamodb" {
  source = "../../modules/data/dynamodb"

  project_name = var.project_name
  environment  = var.environment

  tags = local.common_tags
}

# ── Monitoring ──────────────────────────────────────────────────────────────

module "cloudwatch" {
  source = "../../modules/monitoring/cloudwatch"

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  log_retention_days = var.log_retention_days
  alarm_email        = var.alarm_email

  # AWS allows only one DIMENSIONAL anomaly monitor per account; dev already owns it
  create_cost_anomaly_monitor = false

  tags = local.common_tags
}

# ── Aurora PostgreSQL ───────────────────────────────────────────────────────

module "aurora" {
  source = "../../modules/data/aurora"
  count  = var.enable_aurora ? 1 : 0

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.networking.vpc_id
  vpc_cidr           = module.networking.vpc_cidr
  private_subnet_ids = module.networking.private_subnet_ids
  availability_zones = module.networking.availability_zones

  database_name   = var.aurora_database_name
  master_username = var.aurora_master_username
  master_password = var.aurora_master_password

  min_capacity   = var.aurora_min_capacity
  max_capacity   = var.aurora_max_capacity
  instance_count = var.aurora_instance_count

  deletion_protection         = true
  enable_performance_insights = true
  monitoring_interval         = 60

  create_cloudwatch_alarms = true
  alarm_sns_topic_arn      = module.cloudwatch.alarms_topic_arn

  tags = local.common_tags
}

# ── OpenSearch ──────────────────────────────────────────────────────────────

module "opensearch" {
  source = "../../modules/data/opensearch"
  count  = var.enable_opensearch ? 1 : 0

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.networking.vpc_id
  vpc_cidr           = module.networking.vpc_cidr
  private_subnet_ids = module.networking.private_subnet_ids

  instance_type            = var.opensearch_instance_type
  instance_count           = var.opensearch_instance_count
  dedicated_master_enabled = var.opensearch_dedicated_master_enabled
  zone_awareness_enabled   = var.opensearch_zone_awareness_enabled
  ebs_volume_size          = var.opensearch_ebs_volume_size

  enable_fine_grained_access = true
  master_user_name           = var.opensearch_master_user_name
  master_user_password       = var.opensearch_master_user_password

  create_snapshot_bucket     = true
  create_service_linked_role = var.opensearch_create_service_linked_role

  create_cloudwatch_alarms = true
  alarm_sns_topic_arn      = module.cloudwatch.alarms_topic_arn

  tags = local.common_tags
}

# ── Pipeline ────────────────────────────────────────────────────────────────

module "pipeline" {
  source = "../../modules/pipeline"

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_id             = module.networking.vpc_id
  vpc_cidr           = module.networking.vpc_cidr
  private_subnet_ids = module.networking.private_subnet_ids

  log_retention_days       = var.log_retention_days
  alarm_sns_topic_arn      = module.cloudwatch.alarms_topic_arn
  create_cloudwatch_alarms = true

  enable_schedule     = var.enable_pipeline_schedule
  schedule_expression = var.pipeline_schedule_expression

  db_secret_arn = var.db_secret_arn
  db_host       = try(module.aurora[0].cluster_endpoint, "")
  db_name       = var.aurora_database_name

  tags = local.common_tags
}

# ── Notifications ───────────────────────────────────────────────────────────

module "notifications" {
  source = "../../modules/notifications"

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_id             = module.networking.vpc_id
  vpc_cidr           = module.networking.vpc_cidr
  private_subnet_ids = module.networking.private_subnet_ids

  lambda_security_group_id        = module.pipeline.lambda_security_group_id
  notification_dispatch_queue_arn = module.pipeline.notification_dispatch_queue_arn

  log_retention_days       = var.log_retention_days
  alarm_sns_topic_arn      = module.cloudwatch.alarms_topic_arn
  create_cloudwatch_alarms = true

  bedrock_model_id    = var.messenger_bedrock_model_id
  db_secret_arn       = var.db_secret_arn
  db_host             = try(module.aurora[0].cluster_endpoint, "")
  db_name             = var.aurora_database_name
  ses_sender_email    = var.ses_sender_email

  tags = local.common_tags
}

# ── API ─────────────────────────────────────────────────────────────────────

module "api" {
  source = "../../modules/api"

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_id             = module.networking.vpc_id
  vpc_cidr           = module.networking.vpc_cidr
  private_subnet_ids = module.networking.private_subnet_ids

  lambda_security_group_id = module.pipeline.lambda_security_group_id

  log_retention_days       = var.log_retention_days
  alarm_sns_topic_arn      = module.cloudwatch.alarms_topic_arn
  create_cloudwatch_alarms = true

  db_secret_arn  = var.db_secret_arn
  db_host        = try(module.aurora[0].cluster_endpoint, "")
  db_name        = var.aurora_database_name
  tavily_api_key = var.tavily_api_key
  sns_topic_arn  = module.notifications.sns_topic_arn

  cognito_domain_prefix = var.cognito_domain_prefix
  cognito_callback_urls = var.enable_frontend ? [
    "https://${module.frontend[0].cloudfront_domain_name}/auth/callback",
    "http://localhost:5173/auth/callback",
  ] : ["http://localhost:5173/auth/callback"]
  cognito_logout_urls = var.enable_frontend ? [
    "https://${module.frontend[0].cloudfront_domain_name}/login",
    "http://localhost:5173/login",
  ] : ["http://localhost:5173/login"]

  cors_allowed_origins = var.enable_frontend ? [
    "https://${module.frontend[0].cloudfront_domain_name}",
  ] : ["*"]

  tags = local.common_tags
}

# ── Frontend (Phase 6) ──────────────────────────────────────────────────────

module "frontend" {
  source = "../../modules/frontend"
  count  = var.enable_frontend ? 1 : 0

  project_name = var.project_name
  environment  = var.environment

  tags = local.common_tags
}
