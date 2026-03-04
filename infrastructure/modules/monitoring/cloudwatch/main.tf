# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "application" {
  name              = "/aws/dealfinder/${var.environment}/application"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.tags,
    {
      Name    = "${var.project_name}-${var.environment}-app-logs"
      Purpose = "application-logs"
    }
  )
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.tags,
    {
      Name    = "${var.project_name}-${var.environment}-lambda-logs"
      Purpose = "lambda-logs"
    }
  )
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/aws/ecs/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.tags,
    {
      Name    = "${var.project_name}-${var.environment}-ecs-logs"
      Purpose = "ecs-logs"
    }
  )
}

# SNS Topic for Alarms
resource "aws_sns_topic" "alarms" {
  name = "${var.project_name}-${var.environment}-alarms"

  tags = merge(
    var.tags,
    {
      Name    = "${var.project_name}-${var.environment}-alarms"
      Purpose = "alerting"
    }
  )
}

resource "aws_sns_topic_subscription" "alarms_email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", { stat = "Sum" }],
            [".", "ConsumedWriteCapacityUnits", { stat = "Sum" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "DynamoDB Capacity"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/S3", "BucketSizeBytes", { stat = "Average" }],
            [".", "NumberOfObjects", { stat = "Average" }]
          ]
          period = 86400
          stat   = "Average"
          region = var.aws_region
          title  = "S3 Storage"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", { stat = "Sum" }],
            [".", "Errors", { stat = "Sum" }],
            [".", "Duration", { stat = "Average" }],
            [".", "Throttles", { stat = "Sum" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Lambda Metrics"
        }
      },
      {
        type = "log"
        properties = {
          query   = "SOURCE '${aws_cloudwatch_log_group.application.name}' | fields @timestamp, @message | sort @timestamp desc | limit 20"
          region  = var.aws_region
          title   = "Recent Application Logs"
          stacked = false
        }
      }
    ]
  })
}

# CloudWatch Alarms

# High DynamoDB Read Capacity Alarm
resource "aws_cloudwatch_metric_alarm" "dynamodb_high_read_capacity" {
  alarm_name          = "${var.project_name}-${var.environment}-dynamodb-high-read-capacity"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ConsumedReadCapacityUnits"
  namespace           = "AWS/DynamoDB"
  period              = 300
  statistic           = "Sum"
  threshold           = 80
  alarm_description   = "This metric monitors DynamoDB read capacity"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  tags = var.tags
}

# High DynamoDB Write Capacity Alarm
resource "aws_cloudwatch_metric_alarm" "dynamodb_high_write_capacity" {
  alarm_name          = "${var.project_name}-${var.environment}-dynamodb-high-write-capacity"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ConsumedWriteCapacityUnits"
  namespace           = "AWS/DynamoDB"
  period              = 300
  statistic           = "Sum"
  threshold           = 80
  alarm_description   = "This metric monitors DynamoDB write capacity"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  tags = var.tags
}

# Lambda Error Rate Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "This metric monitors Lambda function errors"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"

  tags = var.tags
}

# Lambda Throttling Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${var.project_name}-${var.environment}-lambda-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "This metric monitors Lambda function throttling"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"

  tags = var.tags
}

# S3 Budget Alert (Custom Metric)
resource "aws_cloudwatch_metric_alarm" "s3_storage_size" {
  alarm_name          = "${var.project_name}-${var.environment}-s3-storage-size"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BucketSizeBytes"
  namespace           = "AWS/S3"
  period              = 86400
  statistic           = "Average"
  threshold           = 107374182400 # 100 GB in bytes
  alarm_description   = "Alert when S3 storage exceeds 100GB"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  tags = var.tags
}

# Cost Anomaly Detection
resource "aws_ce_anomaly_monitor" "dealfinder" {
  name              = "${var.project_name}-${var.environment}-cost-monitor"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"

  tags = var.tags
}

resource "aws_ce_anomaly_subscription" "dealfinder" {
  name      = "${var.project_name}-${var.environment}-cost-anomaly"
  frequency = "DAILY"

  monitor_arn_list = [
    aws_ce_anomaly_monitor.dealfinder.arn
  ]

  subscriber {
    type    = "EMAIL"
    address = var.alarm_email != "" ? var.alarm_email : "noreply@example.com"
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      values        = ["100"]
      match_options = ["GREATER_THAN_OR_EQUAL"]
    }
  }

  tags = var.tags
}
