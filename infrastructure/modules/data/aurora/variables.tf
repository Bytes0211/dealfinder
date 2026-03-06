# Required variables
variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for Aurora cluster"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block for security group rules"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for DB subnet group"
  type        = list(string)
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
}

# Database configuration
variable "database_name" {
  description = "Name of the default database"
  type        = string
  default     = "dealfinder"
}

variable "master_username" {
  description = "Master username for the database"
  type        = string
  default     = "dealfinder_admin"
  sensitive   = true
}

variable "master_password" {
  description = "Master password for the database"
  type        = string
  sensitive   = true
}

variable "engine_version" {
  description = "Aurora PostgreSQL engine version"
  type        = string
  default     = "16.4"
}

# Serverless v2 scaling
variable "min_capacity" {
  description = "Minimum ACUs for Serverless v2 (0.5 to 128)"
  type        = number
  default     = 0.5 # Minimum for cost savings in dev
}

variable "max_capacity" {
  description = "Maximum ACUs for Serverless v2 (0.5 to 128)"
  type        = number
  default     = 4.0 # Reasonable max for dev
}

variable "instance_count" {
  description = "Number of Aurora instances"
  type        = number
  default     = 1 # Single instance for dev
}

# Backup configuration
variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7
}

variable "backup_window" {
  description = "Daily time range for automated backups (UTC)"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "Weekly time range for maintenance (UTC)"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

# Security
variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = false # Disabled for dev
}

variable "create_kms_key" {
  description = "Create dedicated KMS key for encryption"
  type        = bool
  default     = true
}

# Monitoring
variable "monitoring_interval" {
  description = "Enhanced monitoring interval (0 to disable, 1/5/10/15/30/60 seconds)"
  type        = number
  default     = 0 # Disabled by default for cost savings
}

variable "enable_performance_insights" {
  description = "Enable Performance Insights"
  type        = bool
  default     = false # Disabled by default for cost savings
}

variable "enable_query_logging" {
  description = "Enable logging of all SQL statements"
  type        = bool
  default     = false # Disabled by default
}

variable "create_cloudwatch_alarms" {
  description = "Create CloudWatch alarms for monitoring"
  type        = bool
  default     = true
}

variable "alarm_sns_topic_arn" {
  description = "SNS topic ARN for alarm notifications"
  type        = string
  default     = ""
}

# Tags
variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}
