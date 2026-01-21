output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.networking.private_subnet_ids
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.networking.public_subnet_ids
}

output "data_lake_bucket" {
  description = "Data lake S3 bucket name"
  value       = module.s3.data_lake_bucket_name
}

output "models_bucket" {
  description = "Models S3 bucket name"
  value       = module.s3.models_bucket_name
}

output "backups_bucket" {
  description = "Backups S3 bucket name"
  value       = module.s3.backups_bucket_name
}

output "deal_state_table" {
  description = "Deal state DynamoDB table name"
  value       = module.dynamodb.deal_state_table_name
}

output "agent_state_table" {
  description = "Agent state DynamoDB table name"
  value       = module.dynamodb.agent_state_table_name
}

output "user_sessions_table" {
  description = "User sessions DynamoDB table name"
  value       = module.dynamodb.user_sessions_table_name
}

# Monitoring Outputs
output "application_log_group" {
  description = "Name of the application CloudWatch log group"
  value       = module.cloudwatch.application_log_group_name
}

output "lambda_log_group" {
  description = "Name of the Lambda CloudWatch log group"
  value       = module.cloudwatch.lambda_log_group_name
}

output "alarms_topic_arn" {
  description = "ARN of the SNS topic for alarms"
  value       = module.cloudwatch.alarms_topic_arn
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = module.cloudwatch.dashboard_name
}
