variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "dealfinder"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region for resource deployment"
  type        = string
  default     = "us-east-1"
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# Feature flags for enabling/disabling expensive resources
variable "enable_msk" {
  description = "Enable MSK (Kafka) cluster - high cost resource"
  type        = bool
  default     = false
}

variable "enable_opensearch" {
  description = "Enable OpenSearch cluster - high cost resource"
  type        = bool
  default     = false
}

variable "enable_emr" {
  description = "Enable EMR cluster for Spark - high cost resource"
  type        = bool
  default     = false
}

variable "enable_ecs" {
  description = "Enable ECS Fargate for API backend"
  type        = bool
  default     = false
}

variable "enable_sagemaker" {
  description = "Enable SageMaker endpoints for ML models"
  type        = bool
  default     = false
}
