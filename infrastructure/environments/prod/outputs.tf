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

# ── Monitoring ───────────────────────────────────────────────────────────────

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

# ── Aurora ───────────────────────────────────────────────────────────────────

output "aurora_cluster_endpoint" {
  description = "Aurora cluster writer endpoint"
  value       = var.enable_aurora ? module.aurora[0].cluster_endpoint : null
}

output "aurora_reader_endpoint" {
  description = "Aurora cluster reader endpoint"
  value       = var.enable_aurora ? module.aurora[0].cluster_reader_endpoint : null
}

output "aurora_database_name" {
  description = "Aurora database name"
  value       = var.enable_aurora ? module.aurora[0].database_name : null
}

output "aurora_security_group_id" {
  description = "Aurora security group ID"
  value       = var.enable_aurora ? module.aurora[0].security_group_id : null
}

# ── OpenSearch ───────────────────────────────────────────────────────────────

output "opensearch_endpoint" {
  description = "OpenSearch domain endpoint"
  value       = var.enable_opensearch ? module.opensearch[0].domain_endpoint : null
}

output "opensearch_dashboard_endpoint" {
  description = "OpenSearch Dashboards endpoint"
  value       = var.enable_opensearch ? module.opensearch[0].dashboard_endpoint : null
}

output "opensearch_security_group_id" {
  description = "OpenSearch security group ID"
  value       = var.enable_opensearch ? module.opensearch[0].security_group_id : null
}

# ── API ─────────────────────────────────────────────────────────────────────

output "api_endpoint" {
  description = "Base URL of the API Gateway HTTP API"
  value       = module.api.api_endpoint
}

output "cognito_client_id" {
  description = "Cognito user pool client ID"
  value       = module.api.cognito_client_id
}

output "cognito_user_pool_endpoint" {
  description = "Cognito user pool endpoint (use to derive Hosted UI domain)"
  value       = module.api.cognito_user_pool_endpoint
}

# ── Frontend (Phase 6) ───────────────────────────────────────────────────────

output "frontend_bucket_name" {
  description = "S3 bucket name for the React frontend assets"
  value       = var.enable_frontend ? module.frontend[0].bucket_name : null
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for the frontend"
  value       = var.enable_frontend ? module.frontend[0].cloudfront_distribution_id : null
}

output "cloudfront_domain_name" {
  description = "CloudFront domain name (use as the app URL before custom domain)"
  value       = var.enable_frontend ? module.frontend[0].cloudfront_domain_name : null
}

output "frontend_url" {
  description = "Frontend application URL"
  value       = var.enable_frontend ? module.frontend[0].frontend_url : null
}
