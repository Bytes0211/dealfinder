# Aurora PostgreSQL Serverless v2 Cluster
# Cost-optimized for development with production-ready features

locals {
  db_port = 5432
}

# Security Group for Aurora
resource "aws_security_group" "aurora" {
  name        = "${var.project_name}-${var.environment}-aurora-sg"
  description = "Security group for Aurora PostgreSQL cluster"
  vpc_id      = var.vpc_id

  # Allow PostgreSQL traffic from within VPC
  ingress {
    description = "PostgreSQL from VPC"
    from_port   = local.db_port
    to_port     = local.db_port
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
      Name       = "${var.project_name}-${var.environment}-aurora-sg"
      Persistent = "true"
    }
  )
}

# DB Subnet Group
resource "aws_db_subnet_group" "aurora" {
  name        = "${var.project_name}-${var.environment}-aurora-subnet-group"
  description = "Subnet group for Aurora PostgreSQL cluster"
  subnet_ids  = var.private_subnet_ids

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-aurora-subnet-group"
      Persistent = "true"
    }
  )
}

# Parameter Group for PostgreSQL tuning
resource "aws_rds_cluster_parameter_group" "aurora" {
  name        = "${var.project_name}-${var.environment}-aurora-params"
  family      = "aurora-postgresql16"
  description = "Custom parameter group for Aurora PostgreSQL"

  # Enable query logging for debugging
  parameter {
    name         = "log_statement"
    value        = var.enable_query_logging ? "all" : "ddl"
    apply_method = "immediate"
  }

  # Connection timeout
  parameter {
    name         = "idle_in_transaction_session_timeout"
    value        = "300000" # 5 minutes in milliseconds
    apply_method = "immediate"
  }

  # Enable pg_stat_statements for performance monitoring
  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-aurora-params"
      Persistent = "true"
    }
  )
}

# KMS Key for encryption
resource "aws_kms_key" "aurora" {
  count                   = var.create_kms_key ? 1 : 0
  description             = "KMS key for Aurora PostgreSQL encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-aurora-kms"
      Persistent = "true"
    }
  )
}

resource "aws_kms_alias" "aurora" {
  count         = var.create_kms_key ? 1 : 0
  name          = "alias/${var.project_name}-${var.environment}-aurora"
  target_key_id = aws_kms_key.aurora[0].key_id
}

# Aurora PostgreSQL Serverless v2 Cluster
resource "aws_rds_cluster" "aurora" {
  cluster_identifier = "${var.project_name}-${var.environment}-aurora"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = var.engine_version
  database_name      = var.database_name
  master_username    = var.master_username
  master_password    = var.master_password

  # Networking
  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [aws_security_group.aurora.id]
  port                   = local.db_port

  # Serverless v2 scaling configuration
  serverlessv2_scaling_configuration {
    min_capacity = var.min_capacity
    max_capacity = var.max_capacity
  }

  # Security
  storage_encrypted = true
  kms_key_id        = var.create_kms_key ? aws_kms_key.aurora[0].arn : null

  # Backup and recovery
  backup_retention_period   = var.backup_retention_days
  preferred_backup_window   = var.backup_window
  copy_tags_to_snapshot     = true
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.environment == "dev" ? true : false
  final_snapshot_identifier = var.environment == "dev" ? null : "${var.project_name}-${var.environment}-aurora-final-snapshot"

  # Maintenance
  preferred_maintenance_window    = var.maintenance_window
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.aurora.name

  # Monitoring
  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-aurora"
      Persistent = "true"
    }
  )

  lifecycle {
    ignore_changes = [master_password]
  }
}

# Aurora Serverless v2 Instance
resource "aws_rds_cluster_instance" "aurora" {
  count              = var.instance_count
  identifier         = "${var.project_name}-${var.environment}-aurora-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version

  # Monitoring
  monitoring_interval          = var.monitoring_interval
  monitoring_role_arn          = var.monitoring_interval > 0 ? aws_iam_role.rds_monitoring[0].arn : null
  performance_insights_enabled = var.enable_performance_insights

  # Availability
  availability_zone          = var.availability_zones[count.index % length(var.availability_zones)]
  auto_minor_version_upgrade = true
  publicly_accessible        = false

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-aurora-${count.index + 1}"
      Persistent = "true"
    }
  )
}

# IAM Role for Enhanced Monitoring
resource "aws_iam_role" "rds_monitoring" {
  count = var.monitoring_interval > 0 ? 1 : 0
  name  = "${var.project_name}-${var.environment}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  count      = var.monitoring_interval > 0 ? 1 : 0
  role       = aws_iam_role.rds_monitoring[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Secrets Manager — store Aurora credentials so Lambdas can retrieve them
resource "aws_secretsmanager_secret" "aurora" {
  name                    = "${var.project_name}/${var.environment}/aurora"
  description             = "Aurora PostgreSQL credentials for ${var.project_name} ${var.environment}"
  recovery_window_in_days = 0 # Allow immediate deletion in dev

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-aurora-secret"
      Persistent = "true"
    }
  )
}

resource "aws_secretsmanager_secret_version" "aurora" {
  secret_id = aws_secretsmanager_secret.aurora.id
  secret_string = jsonencode({
    username = var.master_username
    password = var.master_password
    host     = aws_rds_cluster.aurora.endpoint
    port     = local.db_port
    dbname   = var.database_name
  })

  lifecycle {
    # Never overwrite the secret after initial creation — credentials may
    # have been rotated independently of Terraform.
    ignore_changes = [secret_string]
  }
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "aurora_cpu" {
  count               = var.create_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-aurora-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Aurora CPU utilization is above 80%"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.aurora.cluster_identifier
  }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "aurora_connections" {
  count               = var.create_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-aurora-high-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 100
  alarm_description   = "Aurora database connections above 100"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.aurora.cluster_identifier
  }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = var.tags
}
