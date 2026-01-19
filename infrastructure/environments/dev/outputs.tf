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
