locals {
  prefix = "${var.project_name}-${var.environment}"
}

# ─────────────────────────────────────────────
# Data Sources
# ─────────────────────────────────────────────

data "aws_caller_identity" "current" {}

# ─────────────────────────────────────────────
# SNS — Deal Notifications Topic
# ─────────────────────────────────────────────

resource "aws_sns_topic" "deal_notifications" {
  name = "${local.prefix}-deal-notifications"
  tags = merge(var.tags, { Name = "${local.prefix}-deal-notifications" })
}

# Optional: SES email subscription (enabled when ses_sender_email is set)
resource "aws_sns_topic_subscription" "email" {
  count     = var.ses_sender_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.deal_notifications.arn
  protocol  = "email"
  endpoint  = var.ses_sender_email
}

# ─────────────────────────────────────────────
# DynamoDB — Notification Deduplication Table
# ─────────────────────────────────────────────

resource "aws_dynamodb_table" "dedup" {
  name         = "${local.prefix}-notif-dedup"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = merge(var.tags, { Name = "${local.prefix}-notif-dedup" })
}

# ─────────────────────────────────────────────
# CloudWatch Log Group — Messenger Lambda
# ─────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "messenger" {
  name              = "/aws/lambda/${local.prefix}-messenger"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

# ─────────────────────────────────────────────
# IAM — Messenger Lambda Role
# ─────────────────────────────────────────────

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "messenger" {
  name               = "${local.prefix}-messenger-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "messenger_vpc" {
  role       = aws_iam_role.messenger.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "messenger_inline" {
  name = "${local.prefix}-messenger-policy"
  role = aws_iam_role.messenger.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "${aws_cloudwatch_log_group.messenger.arn}:*"
      },
      {
        Sid    = "SQSRead"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
        ]
        Resource = var.notification_dispatch_queue_arn
      },
      {
        Sid      = "SNSPublish"
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.deal_notifications.arn
      },
      {
        Sid    = "Bedrock"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:inference-profile/*",
        ]
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
        ]
        Resource = aws_dynamodb_table.dedup.arn
      },
      {
        Sid    = "SecretsManager"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/*",
        ]
      },
      {
        Sid    = "SESEmail"
        Effect = "Allow"
        Action = [
          "sesv2:SendEmail",
        ]
        Resource = "*"
      },
    ]
  })
}

# ─────────────────────────────────────────────
# Lambda placeholder package (shared with pipeline)
# ─────────────────────────────────────────────

data "archive_file" "placeholder" {
  type        = "zip"
  output_path = "${path.module}/placeholder.zip"
  source {
    content  = "# placeholder — replaced by CI/CD\ndef handler(event, context): return {}"
    filename = "handler.py"
  }
}

# ─────────────────────────────────────────────
# Messenger Lambda Function
# ─────────────────────────────────────────────

resource "aws_lambda_function" "messenger" {
  function_name = "${local.prefix}-messenger"
  description   = "MessengerAgent — crafts and dispatches deal notifications"
  role          = aws_iam_role.messenger.arn
  runtime       = var.lambda_runtime
  handler       = "dealfinder.agents.messenger.handler"
  filename      = data.archive_file.placeholder.output_path
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_mb

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  environment {
    variables = {
      DEALFINDER_BEDROCK_REGION   = var.aws_region
      DEALFINDER_BEDROCK_MODEL_ID = var.bedrock_model_id
      DEALFINDER_SES_SENDER_EMAIL = var.ses_sender_email
      DEALFINDER_SNS_TOPIC_ARN    = aws_sns_topic.deal_notifications.arn
      DEALFINDER_DEDUP_TABLE_NAME = aws_dynamodb_table.dedup.name
      DB_HOST                     = var.db_host
      DB_NAME                     = var.db_name
      DB_SECRET_ARN               = var.db_secret_arn
    }
  }

  depends_on = [aws_cloudwatch_log_group.messenger]

  tags = merge(var.tags, { Name = "${local.prefix}-messenger" })

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

# ─────────────────────────────────────────────
# SQS Event Source Mapping
# notification_dispatch → Messenger Lambda
# ─────────────────────────────────────────────

resource "aws_lambda_event_source_mapping" "notification_dispatch" {
  event_source_arn                   = var.notification_dispatch_queue_arn
  function_name                      = aws_lambda_function.messenger.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 30
  # Enable partial batch failure reporting (batchItemFailures response)
  function_response_types = ["ReportBatchItemFailures"]
}

# ─────────────────────────────────────────────
# CloudWatch Alarm — Messenger DLQ depth
# ─────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "messenger_errors" {
  count               = var.create_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${local.prefix}-messenger-errors"
  alarm_description   = "Messenger Lambda error rate — indicates notification dispatch failures"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.messenger.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 3
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alarm_sns_topic_arn]
  tags                = var.tags
}
