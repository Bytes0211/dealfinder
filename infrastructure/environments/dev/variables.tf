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

variable "enable_msk" {
  description = "Enable MSK Kafka cluster (disable to save ~$400-600/month)"
  type        = bool
  default     = false
}

variable "enable_opensearch" {
  description = "Enable OpenSearch cluster (disable to save ~$300-500/month)"
  type        = bool
  default     = false
}

variable "enable_emr" {
  description = "Enable EMR cluster (disable to save ~$100-200/month)"
  type        = bool
  default     = false
}

variable "enable_ecs" {
  description = "Enable ECS Fargate (disable to save ~$200-300/month)"
  type        = bool
  default     = false
}

variable "enable_sagemaker" {
  description = "Enable SageMaker endpoints (disable to save costs)"
  type        = bool
  default     = false
}
