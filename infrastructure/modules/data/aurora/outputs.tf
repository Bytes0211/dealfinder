output "cluster_id" {
  description = "Aurora cluster identifier"
  value       = aws_rds_cluster.aurora.id
}

output "cluster_arn" {
  description = "Aurora cluster ARN"
  value       = aws_rds_cluster.aurora.arn
}

output "cluster_endpoint" {
  description = "Writer endpoint for the Aurora cluster"
  value       = aws_rds_cluster.aurora.endpoint
}

output "cluster_reader_endpoint" {
  description = "Reader endpoint for the Aurora cluster"
  value       = aws_rds_cluster.aurora.reader_endpoint
}

output "cluster_port" {
  description = "Database port"
  value       = aws_rds_cluster.aurora.port
}

output "database_name" {
  description = "Name of the default database"
  value       = aws_rds_cluster.aurora.database_name
}

output "master_username" {
  description = "Master username"
  value       = aws_rds_cluster.aurora.master_username
  sensitive   = true
}

output "security_group_id" {
  description = "Security group ID for Aurora"
  value       = aws_security_group.aurora.id
}

output "db_subnet_group_name" {
  description = "DB subnet group name"
  value       = aws_db_subnet_group.aurora.name
}

output "parameter_group_name" {
  description = "Cluster parameter group name"
  value       = aws_rds_cluster_parameter_group.aurora.name
}

output "kms_key_arn" {
  description = "KMS key ARN used for encryption"
  value       = var.create_kms_key ? aws_kms_key.aurora[0].arn : null
}

output "instance_ids" {
  description = "List of Aurora instance identifiers"
  value       = aws_rds_cluster_instance.aurora[*].id
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret containing Aurora credentials"
  value       = aws_secretsmanager_secret.aurora.arn
}

output "connection_string" {
  description = "PostgreSQL connection string (without password)"
  value       = "postgresql://${aws_rds_cluster.aurora.master_username}@${aws_rds_cluster.aurora.endpoint}:${aws_rds_cluster.aurora.port}/${aws_rds_cluster.aurora.database_name}"
  sensitive   = true
}
