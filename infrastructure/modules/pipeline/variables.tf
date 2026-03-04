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

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "alarm_sns_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarms"
  type        = string
  default     = ""
}

# EventBridge schedule
variable "enable_schedule" {
  description = "Enable EventBridge schedule to trigger the pipeline automatically"
  type        = bool
  default     = false
}

variable "schedule_expression" {
  description = "EventBridge schedule expression (cron or rate)"
  type        = string
  default     = "rate(15 minutes)"
}

# Lambda configuration
variable "lambda_memory_mb" {
  description = "Memory allocation for Lambda functions in MB"
  type        = number
  default     = 256
}

variable "lambda_timeout_seconds" {
  description = "Timeout for Lambda functions in seconds"
  type        = number
  default     = 300
}

variable "lambda_runtime" {
  description = "Lambda runtime identifier"
  type        = string
  default     = "python3.12"
}

# Agent configuration
variable "discount_threshold" {
  description = "Minimum discount percentage to flag a deal as high value"
  type        = number
  default     = 20.0
}

variable "bedrock_model_id" {
  description = "AWS Bedrock model ID for price estimation"
  type        = string
  default     = "anthropic.claude-3-sonnet-20240229-v1:0"
}

# SQS configuration
variable "sqs_message_retention_seconds" {
  description = "SQS message retention period in seconds (default 4 days)"
  type        = number
  default     = 345600
}

variable "sqs_visibility_timeout_seconds" {
  description = "SQS visibility timeout — should exceed Lambda timeout"
  type        = number
  default     = 360
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
