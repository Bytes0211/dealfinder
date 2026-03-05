variable "project_name" {
  description = "Project name"
  type        = string
  default     = "dealfinder"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.1.0.0/16"
}

# ── Cost-saving feature flags ────────────────────────────────────────────────

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway (disable to save ~$100/month)"
  type        = bool
  default     = true # Enabled in prod for Lambda internet access
}

variable "enable_aurora" {
  description = "Enable Aurora PostgreSQL cluster (disable to save ~$50-100/month)"
  type        = bool
  default     = true # Required in prod
}

variable "enable_opensearch" {
  description = "Enable OpenSearch cluster (disable to save ~$300-500/month)"
  type        = bool
  default     = false # Enable when vector search is needed
}

variable "enable_frontend" {
  description = "Enable React frontend (S3 + CloudFront static site)"
  type        = bool
  default     = false # Enable when frontend is ready to deploy
}

# ── Monitoring ───────────────────────────────────────────────────────────────

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 90
}

variable "alarm_email" {
  description = "Email address for alarm notifications"
  type        = string
  default     = ""
}

# ── Aurora PostgreSQL ────────────────────────────────────────────────────────

variable "aurora_database_name" {
  description = "Name of the default database"
  type        = string
  default     = "dealfinder"
}

variable "aurora_master_username" {
  description = "Master username for Aurora"
  type        = string
  default     = "dealfinder_admin"
  sensitive   = true
}

variable "aurora_master_password" {
  description = "Master password for Aurora"
  type        = string
  sensitive   = true
  default     = "" # Must be set via terraform.tfvars or environment variable
}

variable "aurora_min_capacity" {
  description = "Minimum ACUs for Aurora Serverless v2"
  type        = number
  default     = 0.5
}

variable "aurora_max_capacity" {
  description = "Maximum ACUs for Aurora Serverless v2"
  type        = number
  default     = 8.0
}

variable "aurora_instance_count" {
  description = "Number of Aurora instances"
  type        = number
  default     = 2 # Writer + reader in prod
}

# ── OpenSearch ───────────────────────────────────────────────────────────────

variable "opensearch_instance_type" {
  description = "Instance type for OpenSearch data nodes"
  type        = string
  default     = "m6g.large.search"
}

variable "opensearch_instance_count" {
  description = "Number of OpenSearch data nodes"
  type        = number
  default     = 2
}

variable "opensearch_dedicated_master_enabled" {
  description = "Enable dedicated master nodes"
  type        = bool
  default     = false
}

variable "opensearch_zone_awareness_enabled" {
  description = "Enable multi-AZ deployment"
  type        = bool
  default     = true
}

variable "opensearch_ebs_volume_size" {
  description = "EBS volume size in GB"
  type        = number
  default     = 50
}

variable "opensearch_master_user_name" {
  description = "Master user name for OpenSearch"
  type        = string
  default     = "admin"
  sensitive   = true
}

variable "opensearch_master_user_password" {
  description = "Master user password for OpenSearch"
  type        = string
  sensitive   = true
  default     = "" # Must be set via terraform.tfvars or environment variable
}

variable "opensearch_create_service_linked_role" {
  description = "Create OpenSearch service-linked role (set false if already exists)"
  type        = bool
  default     = true
}

# ── Pipeline ─────────────────────────────────────────────────────────────────

variable "db_secret_arn" {
  description = "ARN of Secrets Manager secret with Aurora DB credentials"
  type        = string
  default     = ""
}

variable "enable_pipeline_schedule" {
  description = "Enable EventBridge schedule to run the pipeline automatically"
  type        = bool
  default     = true # Always-on in prod
}

variable "pipeline_schedule_expression" {
  description = "EventBridge schedule expression for the pipeline (cron or rate)"
  type        = string
  default     = "rate(15 minutes)"
}

# ── Notifications ────────────────────────────────────────────────────────────

variable "ses_sender_email" {
  description = "Verified SES sender email address for deal alert emails"
  type        = string
  default     = ""
}

variable "messenger_bedrock_model_id" {
  description = "Bedrock model ID for the MessengerAgent"
  type        = string
  default     = "anthropic.claude-3-sonnet-20240229-v1:0"
}

# ── Cognito Hosted UI ────────────────────────────────────────────────────────

variable "cognito_domain_prefix" {
  description = "Prefix for Cognito Hosted UI domain (must be globally unique, e.g. 'dealfinder-prod-abc123')"
  type        = string
  default     = "dealfinder-prod"
}
