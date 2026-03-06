output "domain_id" {
  description = "OpenSearch domain ID"
  value       = aws_opensearch_domain.main.domain_id
}

output "domain_name" {
  description = "OpenSearch domain name"
  value       = aws_opensearch_domain.main.domain_name
}

output "domain_arn" {
  description = "OpenSearch domain ARN"
  value       = aws_opensearch_domain.main.arn
}

output "domain_endpoint" {
  description = "OpenSearch domain endpoint"
  value       = aws_opensearch_domain.main.endpoint
}

output "dashboard_endpoint" {
  description = "OpenSearch Dashboards endpoint"
  value       = aws_opensearch_domain.main.dashboard_endpoint
}

output "security_group_id" {
  description = "Security group ID for OpenSearch"
  value       = aws_security_group.opensearch.id
}

output "kms_key_arn" {
  description = "KMS key ARN used for encryption"
  value       = var.create_kms_key ? aws_kms_key.opensearch[0].arn : null
}

output "snapshot_bucket_name" {
  description = "S3 bucket name for snapshots"
  value       = var.create_snapshot_bucket ? aws_s3_bucket.opensearch_snapshots[0].bucket : null
}

output "snapshot_bucket_arn" {
  description = "S3 bucket ARN for snapshots"
  value       = var.create_snapshot_bucket ? aws_s3_bucket.opensearch_snapshots[0].arn : null
}

output "snapshot_role_arn" {
  description = "IAM role ARN for snapshot operations"
  value       = var.create_snapshot_bucket ? aws_iam_role.opensearch_snapshot[0].arn : null
}

output "engine_version" {
  description = "OpenSearch engine version"
  value       = aws_opensearch_domain.main.engine_version
}

output "instance_type" {
  description = "Instance type used for data nodes"
  value       = var.instance_type
}

output "instance_count" {
  description = "Number of data nodes"
  value       = var.instance_count
}

output "https_endpoint" {
  description = "Full HTTPS endpoint for OpenSearch"
  value       = "https://${aws_opensearch_domain.main.endpoint}"
}

output "kibana_url" {
  description = "URL for OpenSearch Dashboards (Kibana)"
  value       = "https://${aws_opensearch_domain.main.dashboard_endpoint}/_dashboards"
}
