variable "project_name" {
  description = "Project name used as a prefix for all resources"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for Lambda networking"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for Lambda functions"
  type        = list(string)
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC — scopes PostgreSQL egress"
  type        = string
}

variable "lambda_security_group_id" {
  description = "Security group ID from the pipeline module to reuse for Messenger Lambda"
  type        = string
}

variable "notification_dispatch_queue_arn" {
  description = "ARN of the notification-dispatch SQS queue (event source for Messenger)"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "lambda_memory_mb" {
  description = "Memory allocation for the Messenger Lambda in MB"
  type        = number
  default     = 256
}

variable "lambda_timeout_seconds" {
  description = "Timeout for the Messenger Lambda in seconds"
  type        = number
  default     = 300
}

variable "lambda_runtime" {
  description = "Lambda runtime identifier"
  type        = string
  default     = "python3.12"
}

variable "bedrock_model_id" {
  description = "AWS Bedrock model ID for message crafting (set from config/bedrock_models.json)"
  type        = string
}

variable "db_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Aurora DB credentials"
  type        = string
  default     = ""
}

variable "db_host" {
  description = "Aurora cluster writer endpoint hostname"
  type        = string
  default     = ""
}

variable "db_name" {
  description = "Aurora database name"
  type        = string
  default     = "dealfinder"
}

variable "ses_sender_email" {
  description = "Verified SES sender email address for deal alert emails"
  type        = string
  default     = ""
}

variable "alarm_sns_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarms"
  type        = string
  default     = ""
}

variable "create_cloudwatch_alarms" {
  description = "Whether to create CloudWatch alarms (requires alarm_sns_topic_arn)"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
