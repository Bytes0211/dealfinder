# OpenSearch Domain for Vector Search
# Configured with k-NN plugin for semantic search capabilities

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  domain_name = "${var.project_name}-${var.environment}"
}

# Security Group for OpenSearch
resource "aws_security_group" "opensearch" {
  name        = "${var.project_name}-${var.environment}-opensearch-sg"
  description = "Security group for OpenSearch domain"
  vpc_id      = var.vpc_id

  # HTTPS access from VPC
  ingress {
    description = "HTTPS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  # Allow all outbound traffic
  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-opensearch-sg"
      Persistent = "false" # Destroyable for cost savings
    }
  )
}

# IAM Service-Linked Role for OpenSearch VPC access
resource "aws_iam_service_linked_role" "opensearch" {
  count            = var.create_service_linked_role ? 1 : 0
  aws_service_name = "opensearchservice.amazonaws.com"
}

# KMS Key for encryption
resource "aws_kms_key" "opensearch" {
  count                   = var.create_kms_key ? 1 : 0
  description             = "KMS key for OpenSearch encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-opensearch-kms"
      Persistent = "false"
    }
  )
}

resource "aws_kms_alias" "opensearch" {
  count         = var.create_kms_key ? 1 : 0
  name          = "alias/${var.project_name}-${var.environment}-opensearch"
  target_key_id = aws_kms_key.opensearch[0].key_id
}

# CloudWatch Log Group for OpenSearch
resource "aws_cloudwatch_log_group" "opensearch" {
  name              = "/aws/opensearch/${local.domain_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# Log Resource Policy for OpenSearch
resource "aws_cloudwatch_log_resource_policy" "opensearch" {
  policy_name = "${var.project_name}-${var.environment}-opensearch-log-policy"

  policy_document = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "es.amazonaws.com"
        }
        Action = [
          "logs:PutLogEvents",
          "logs:PutLogEventsBatch",
          "logs:CreateLogStream"
        ]
        Resource = "${aws_cloudwatch_log_group.opensearch.arn}:*"
      }
    ]
  })
}

# OpenSearch Domain
resource "aws_opensearch_domain" "main" {
  domain_name    = local.domain_name
  engine_version = var.engine_version

  # Cluster configuration
  cluster_config {
    instance_type            = var.instance_type
    instance_count           = var.instance_count
    dedicated_master_enabled = var.dedicated_master_enabled
    dedicated_master_type    = var.dedicated_master_enabled ? var.dedicated_master_type : null
    dedicated_master_count   = var.dedicated_master_enabled ? var.dedicated_master_count : null
    zone_awareness_enabled   = var.zone_awareness_enabled

    dynamic "zone_awareness_config" {
      for_each = var.zone_awareness_enabled ? [1] : []
      content {
        availability_zone_count = min(var.instance_count, 3)
      }
    }

    # Warm storage (optional for cost optimization)
    warm_enabled = var.warm_enabled
    warm_type    = var.warm_enabled ? var.warm_type : null
    warm_count   = var.warm_enabled ? var.warm_count : null
  }

  # VPC configuration
  vpc_options {
    subnet_ids         = var.zone_awareness_enabled ? slice(var.private_subnet_ids, 0, min(var.instance_count, 3)) : [var.private_subnet_ids[0]]
    security_group_ids = [aws_security_group.opensearch.id]
  }

  # EBS storage
  ebs_options {
    ebs_enabled = true
    volume_type = var.ebs_volume_type
    volume_size = var.ebs_volume_size
    iops        = var.ebs_volume_type == "gp3" ? var.ebs_iops : null
    throughput  = var.ebs_volume_type == "gp3" ? var.ebs_throughput : null
  }

  # Encryption
  encrypt_at_rest {
    enabled    = true
    kms_key_id = var.create_kms_key ? aws_kms_key.opensearch[0].key_id : null
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  # Advanced security options (fine-grained access control)
  advanced_security_options {
    enabled                        = var.enable_fine_grained_access
    internal_user_database_enabled = var.enable_fine_grained_access
    anonymous_auth_enabled         = false

    dynamic "master_user_options" {
      for_each = var.enable_fine_grained_access ? [1] : []
      content {
        master_user_name     = var.master_user_name
        master_user_password = var.master_user_password
      }
    }
  }

  # Snapshot configuration
  snapshot_options {
    automated_snapshot_start_hour = var.snapshot_start_hour
  }

  # Logging
  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch.arn
    log_type                 = "INDEX_SLOW_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch.arn
    log_type                 = "SEARCH_SLOW_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch.arn
    log_type                 = "ES_APPLICATION_LOGS"
  }

  # Advanced options for k-NN
  advanced_options = {
    "rest.action.multi.allow_explicit_index" = "true"
    "indices.query.bool.max_clause_count"    = "1024"
    "override_main_response_version"         = "false"
  }

  # Access policy - allow access from VPC
  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "*"
        }
        Action   = "es:*"
        Resource = "arn:aws:es:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:domain/${local.domain_name}/*"
        Condition = {
          IpAddress = {
            "aws:SourceIp" = var.vpc_cidr
          }
        }
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-opensearch"
      Persistent = "false" # Destroyable for cost savings
    }
  )

  depends_on = [
    aws_iam_service_linked_role.opensearch,
    aws_cloudwatch_log_resource_policy.opensearch
  ]
}

# S3 bucket for manual snapshots
resource "aws_s3_bucket" "opensearch_snapshots" {
  count  = var.create_snapshot_bucket ? 1 : 0
  bucket = "${var.project_name}-${var.environment}-opensearch-snapshots"

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-opensearch-snapshots"
      Purpose    = "opensearch-snapshots"
      Persistent = "true" # Keep snapshots even if domain is destroyed
    }
  )
}

resource "aws_s3_bucket_versioning" "opensearch_snapshots" {
  count  = var.create_snapshot_bucket ? 1 : 0
  bucket = aws_s3_bucket.opensearch_snapshots[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "opensearch_snapshots" {
  count  = var.create_snapshot_bucket ? 1 : 0
  bucket = aws_s3_bucket.opensearch_snapshots[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "opensearch_snapshots" {
  count  = var.create_snapshot_bucket ? 1 : 0
  bucket = aws_s3_bucket.opensearch_snapshots[0].id

  rule {
    id     = "snapshot-lifecycle"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}

# IAM Role for OpenSearch to access S3 snapshots
resource "aws_iam_role" "opensearch_snapshot" {
  count = var.create_snapshot_bucket ? 1 : 0
  name  = "${var.project_name}-${var.environment}-opensearch-snapshot-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "es.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "opensearch_snapshot" {
  count = var.create_snapshot_bucket ? 1 : 0
  name  = "${var.project_name}-${var.environment}-opensearch-snapshot-policy"
  role  = aws_iam_role.opensearch_snapshot[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.opensearch_snapshots[0].arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.opensearch_snapshots[0].arn}/*"
      }
    ]
  })
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "cluster_status_red" {
  count               = var.create_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-opensearch-cluster-red"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ClusterStatus.red"
  namespace           = "AWS/ES"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "OpenSearch cluster status is RED"

  dimensions = {
    DomainName = aws_opensearch_domain.main.domain_name
    ClientId   = data.aws_caller_identity.current.account_id
  }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "free_storage_space" {
  count               = var.create_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-opensearch-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/ES"
  period              = 300
  statistic           = "Minimum"
  threshold           = var.ebs_volume_size * 1024 * 0.2 # 20% of total storage in MB
  alarm_description   = "OpenSearch free storage space below 20%"

  dimensions = {
    DomainName = aws_opensearch_domain.main.domain_name
    ClientId   = data.aws_caller_identity.current.account_id
  }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "cpu_utilization" {
  count               = var.create_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-opensearch-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ES"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "OpenSearch CPU utilization above 80%"

  dimensions = {
    DomainName = aws_opensearch_domain.main.domain_name
    ClientId   = data.aws_caller_identity.current.account_id
  }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = var.tags
}
