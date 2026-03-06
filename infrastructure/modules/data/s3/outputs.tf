output "data_lake_bucket_name" {
  description = "Data lake bucket name"
  value       = aws_s3_bucket.data_lake.bucket
}

output "data_lake_bucket_arn" {
  description = "Data lake bucket ARN"
  value       = aws_s3_bucket.data_lake.arn
}

output "models_bucket_name" {
  description = "Models bucket name"
  value       = aws_s3_bucket.models.bucket
}

output "models_bucket_arn" {
  description = "Models bucket ARN"
  value       = aws_s3_bucket.models.arn
}

output "backups_bucket_name" {
  description = "Backups bucket name"
  value       = aws_s3_bucket.backups.bucket
}

output "backups_bucket_arn" {
  description = "Backups bucket ARN"
  value       = aws_s3_bucket.backups.arn
}
