variable "project_name" {
  description = "Project name"
  type        = string
  default     = "dealfinder"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# Cost-saving feature flags
variable "enable_nat_gateway" {
  description = "Enable NAT Gateway (disable to save ~$100/month)"
  type        = bool
  default     = false # Disabled by default for dev
}

variable "enable_opensearch" {
  description = "Enable OpenSearch cluster (disable to save ~$300-500/month)"
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "alarm_email" {
  description = "Email address for alarm notifications"
  type        = string
  default     = ""
}

# Aurora PostgreSQL variables
variable "enable_aurora" {
  description = "Enable Aurora PostgreSQL cluster (disable to save ~$50-100/month)"
  type        = bool
  default     = false
}

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
  default     = 4.0
}

variable "aurora_instance_count" {
  description = "Number of Aurora instances"
  type        = number
  default     = 1
}

# OpenSearch variables
variable "opensearch_instance_type" {
  description = "Instance type for OpenSearch data nodes"
  type        = string
  default     = "t3.small.search"
}

variable "opensearch_instance_count" {
  description = "Number of OpenSearch data nodes"
  type        = number
  default     = 1
}

variable "opensearch_dedicated_master_enabled" {
  description = "Enable dedicated master nodes"
  type        = bool
  default     = false
}

variable "opensearch_zone_awareness_enabled" {
  description = "Enable multi-AZ deployment"
  type        = bool
  default     = false
}

variable "opensearch_ebs_volume_size" {
  description = "EBS volume size in GB"
  type        = number
  default     = 20
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

# Pipeline (Phase 3)
variable "db_secret_arn" {
  description = "ARN of Secrets Manager secret with Aurora DB credentials (empty when Aurora disabled)"
  type        = string
  default     = ""
}

variable "enable_pipeline_schedule" {
  description = "Enable EventBridge schedule to run the pipeline automatically"
  type        = bool
  default     = false # Disabled by default to prevent unintended executions in dev
}

variable "pipeline_schedule_expression" {
  description = "EventBridge schedule expression for the pipeline (cron or rate)"
  type        = string
  default     = "rate(15 minutes)"
}
