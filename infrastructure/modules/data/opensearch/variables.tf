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
  description = "VPC ID for OpenSearch domain"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block for access policies"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for VPC deployment"
  type        = list(string)
}

# Engine configuration
variable "engine_version" {
  description = "OpenSearch engine version"
  type        = string
  default     = "OpenSearch_2.11" # Latest stable version with k-NN support
}

# Cluster configuration
variable "instance_type" {
  description = "Instance type for data nodes"
  type        = string
  default     = "t3.small.search" # Cost-effective for dev
}

variable "instance_count" {
  description = "Number of data nodes"
  type        = number
  default     = 1 # Single node for dev
}

variable "dedicated_master_enabled" {
  description = "Enable dedicated master nodes"
  type        = bool
  default     = false # Disabled for dev
}

variable "dedicated_master_type" {
  description = "Instance type for dedicated master nodes"
  type        = string
  default     = "t3.small.search"
}

variable "dedicated_master_count" {
  description = "Number of dedicated master nodes (must be 3 or 5)"
  type        = number
  default     = 3
}

variable "zone_awareness_enabled" {
  description = "Enable multi-AZ deployment"
  type        = bool
  default     = false # Disabled for dev (single AZ)
}

# Warm storage
variable "warm_enabled" {
  description = "Enable warm storage tier"
  type        = bool
  default     = false
}

variable "warm_type" {
  description = "Instance type for warm nodes"
  type        = string
  default     = "ultrawarm1.medium.search"
}

variable "warm_count" {
  description = "Number of warm nodes"
  type        = number
  default     = 2
}

# EBS storage
variable "ebs_volume_type" {
  description = "EBS volume type (gp2, gp3, io1)"
  type        = string
  default     = "gp3"
}

variable "ebs_volume_size" {
  description = "EBS volume size in GB"
  type        = number
  default     = 20 # Minimum for dev
}

variable "ebs_iops" {
  description = "IOPS for gp3 volumes"
  type        = number
  default     = 3000
}

variable "ebs_throughput" {
  description = "Throughput for gp3 volumes (MB/s)"
  type        = number
  default     = 125
}

# Security
variable "create_kms_key" {
  description = "Create dedicated KMS key for encryption"
  type        = bool
  default     = true
}

variable "create_service_linked_role" {
  description = "Create IAM service-linked role for OpenSearch"
  type        = bool
  default     = true
}

variable "enable_fine_grained_access" {
  description = "Enable fine-grained access control"
  type        = bool
  default     = true
}

variable "master_user_name" {
  description = "Master user name for fine-grained access"
  type        = string
  default     = "admin"
  sensitive   = true
}

variable "master_user_password" {
  description = "Master user password for fine-grained access"
  type        = string
  sensitive   = true
}

# Snapshots
variable "snapshot_start_hour" {
  description = "Hour (UTC) for automated snapshot"
  type        = number
  default     = 3
}

variable "create_snapshot_bucket" {
  description = "Create S3 bucket for manual snapshots"
  type        = bool
  default     = true
}

# Logging
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

# Monitoring
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
