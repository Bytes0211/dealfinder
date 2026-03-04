locals {
  prefix = "${var.project_name}-${var.environment}"
}

# ─────────────────────────────────────────────
# SQS — Deal Processing Queue
# ─────────────────────────────────────────────
# Reserved for Phase 4 Messenger Agent as a downstream subscriber to scanner output.
# Keeps scanner discoveries available for additional consumers without tight coupling.

resource "aws_sqs_queue" "deal_processing_dlq" {
  name                       = "${local.prefix}-deal-processing-dlq"
  message_retention_seconds  = 1209600 # 14 days — long retention for investigation
  kms_master_key_id          = "alias/aws/sqs"

  tags = merge(var.tags, { Name = "${local.prefix}-deal-processing-dlq" })
}

resource "aws_sqs_queue" "deal_processing" {
  name                       = "${local.prefix}-deal-processing"
  visibility_timeout_seconds = var.sqs_visibility_timeout_seconds
  message_retention_seconds  = var.sqs_message_retention_seconds
  kms_master_key_id          = "alias/aws/sqs"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.deal_processing_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(var.tags, { Name = "${local.prefix}-deal-processing" })
}

# ─────────────────────────────────────────────
# SQS — Notification Dispatch Queue
# ─────────────────────────────────────────────

resource "aws_sqs_queue" "notification_dispatch_dlq" {
  name                      = "${local.prefix}-notification-dispatch-dlq"
  message_retention_seconds = 1209600
  kms_master_key_id         = "alias/aws/sqs"

  tags = merge(var.tags, { Name = "${local.prefix}-notification-dispatch-dlq" })
}

resource "aws_sqs_queue" "notification_dispatch" {
  name                       = "${local.prefix}-notification-dispatch"
  visibility_timeout_seconds = var.sqs_visibility_timeout_seconds
  message_retention_seconds  = var.sqs_message_retention_seconds
  kms_master_key_id          = "alias/aws/sqs"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notification_dispatch_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(var.tags, { Name = "${local.prefix}-notification-dispatch" })
}

# ─────────────────────────────────────────────
# CloudWatch Log Groups for Lambda
# ─────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "scanner" {
  name              = "/aws/lambda/${local.prefix}-scanner"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "evaluator" {
  name              = "/aws/lambda/${local.prefix}-evaluator"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

# ─────────────────────────────────────────────
# IAM — Lambda Execution Roles
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

# Scanner Lambda role
resource "aws_iam_role" "scanner" {
  name               = "${local.prefix}-scanner-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "scanner_basic" {
  role       = aws_iam_role.scanner.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "scanner_inline" {
  name = "${local.prefix}-scanner-policy"
  role = aws_iam_role.scanner.id

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
        Resource = "${aws_cloudwatch_log_group.scanner.arn}:*"
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:*:table/${var.project_name}-${var.environment}-*"
      },
      {
        Sid    = "SecretsManager"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.project_name}/${var.environment}/*"
      },
    ]
  })
}

# Evaluator Lambda role
resource "aws_iam_role" "evaluator" {
  name               = "${local.prefix}-evaluator-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "evaluator_basic" {
  role       = aws_iam_role.evaluator.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "evaluator_inline" {
  name = "${local.prefix}-evaluator-policy"
  role = aws_iam_role.evaluator.id

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
        Resource = "${aws_cloudwatch_log_group.evaluator.arn}:*"
      },
      {
        Sid    = "Bedrock"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:*:table/${var.project_name}-${var.environment}-*"
      },
      {
        Sid    = "SecretsManager"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.project_name}/${var.environment}/*"
      },
    ]
  })
}

# ─────────────────────────────────────────────
# Lambda Security Group (VPC)
# ─────────────────────────────────────────────

resource "aws_security_group" "lambda" {
  name        = "${local.prefix}-lambda-sg"
  description = "Outbound-only security group for pipeline Lambda functions"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound (HTTPS to AWS services)"
  }

  tags = merge(var.tags, { Name = "${local.prefix}-lambda-sg" })
}

# ─────────────────────────────────────────────
# Lambda placeholder package
# CI/CD will replace this zip with the real build.
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
# Lambda Functions
# ─────────────────────────────────────────────

resource "aws_lambda_function" "scanner" {
  function_name = "${local.prefix}-scanner"
  description   = "ScannerAgent — fetches RSS feeds and persists new deals"
  role          = aws_iam_role.scanner.arn
  runtime       = var.lambda_runtime
  handler       = "dealfinder.agents.scanner.handler"
  filename      = data.archive_file.placeholder.output_path
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_mb

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DEALFINDER_DISCOUNT_THRESHOLD = tostring(var.discount_threshold)
      DEALFINDER_BEDROCK_REGION     = var.aws_region
      DEALFINDER_BEDROCK_MODEL_ID   = var.bedrock_model_id
      DB_HOST                       = var.db_host
      DB_NAME                       = var.db_name
      DB_SECRET_ARN                 = var.db_secret_arn
    }
  }

  depends_on = [aws_cloudwatch_log_group.scanner]

  tags = merge(var.tags, { Name = "${local.prefix}-scanner" })

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

resource "aws_lambda_function" "evaluator" {
  function_name = "${local.prefix}-evaluator"
  description   = "EvaluatorAgent — estimates price via Bedrock and calculates discounts"
  role          = aws_iam_role.evaluator.arn
  runtime       = var.lambda_runtime
  handler       = "dealfinder.agents.evaluator.handler"
  filename      = data.archive_file.placeholder.output_path
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_mb

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DEALFINDER_DISCOUNT_THRESHOLD = tostring(var.discount_threshold)
      DEALFINDER_BEDROCK_REGION     = var.aws_region
      DEALFINDER_BEDROCK_MODEL_ID   = var.bedrock_model_id
      DB_HOST                       = var.db_host
      DB_NAME                       = var.db_name
      DB_SECRET_ARN                 = var.db_secret_arn
    }
  }

  depends_on = [aws_cloudwatch_log_group.evaluator]

  tags = merge(var.tags, { Name = "${local.prefix}-evaluator" })

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

# ─────────────────────────────────────────────
# IAM — Step Functions Execution Role
# ─────────────────────────────────────────────

data "aws_iam_policy_document" "sfn_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "step_functions" {
  name               = "${local.prefix}-sfn-pipeline-role"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "step_functions_inline" {
  name = "${local.prefix}-sfn-pipeline-policy"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeLambda"
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = [
          aws_lambda_function.scanner.arn,
          aws_lambda_function.evaluator.arn,
        ]
      },
      {
        Sid    = "SendSQS"
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = [
          aws_sqs_queue.notification_dispatch.arn,
        ]
      },
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutLogEvents",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups",
        ]
        Resource = "*"
      },
    ]
  })
}

# ─────────────────────────────────────────────
# Step Functions State Machine
# ─────────────────────────────────────────────

resource "aws_sfn_state_machine" "pipeline" {
  name     = "${local.prefix}-pipeline"
  role_arn = aws_iam_role.step_functions.arn

  definition = jsonencode({
    Comment = "Deal Finder pipeline: Scan → Evaluate → Notify"
    StartAt = "ScanFeeds"
    States = {
      ScanFeeds = {
        Type     = "Task"
        Resource = aws_lambda_function.scanner.arn
        Comment  = "Fetch RSS feeds and persist new deals; returns new_deal_ids list"
        ResultPath = "$"
        Next = "ProcessDeals"
        Retry = [
          {
            ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
            IntervalSeconds = 2
            MaxAttempts     = 3
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "PipelineFailed"
            ResultPath  = "$.error"
          }
        ]
      }

      ProcessDeals = {
        Type           = "Map"
        Comment        = "Evaluate each newly discovered deal in parallel (max 5)"
        ItemsPath      = "$.new_deal_ids"
        MaxConcurrency = 5
        ItemSelector = {
          "deal_id.$" = "$$.Map.Item.Value"
        }
        Iterator = {
          StartAt = "EvaluateDeal"
          States = {
            EvaluateDeal = {
              Type     = "Task"
              Resource = aws_lambda_function.evaluator.arn
              Comment  = "Estimate price via Bedrock and calculate discount"
              ResultPath = "$"
              Next = "IsHighValue"
              Retry = [
                {
                  ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException"]
                  IntervalSeconds = 2
                  MaxAttempts     = 2
                  BackoffRate     = 2.0
                }
              ]
              Catch = [
                {
                  ErrorEquals = ["States.ALL"]
                  Next        = "DealFailed"
                  ResultPath  = "$.error"
                }
              ]
            }
            IsHighValue = {
              Type    = "Choice"
              Comment = "Route high-value deals to the notification queue"
              Choices = [
                {
                  Variable      = "$.is_high_value"
                  BooleanEquals = true
                  Next          = "QueueNotification"
                }
              ]
              Default = "DealProcessed"
            }
            QueueNotification = {
              Type     = "Task"
              Resource = "arn:aws:states:::sqs:sendMessage"
              Comment  = "Enqueue deal_id for the Messenger Agent (Phase 4)"
              Parameters = {
                QueueUrl       = aws_sqs_queue.notification_dispatch.url
                "MessageBody.$" = "$.deal_id"
              }
              ResultPath = null
              Next       = "DealProcessed"
            }
            DealProcessed = {
              Type = "Pass"
              End  = true
            }
            DealFailed = {
              Type  = "Fail"
              Error = "DealEvaluationError"
              Cause = "EvaluatorAgent failed; see CloudWatch logs for details"
            }
          }
        }
        Next = "PipelineComplete"
      }

      PipelineComplete = {
        Type = "Pass"
        End  = true
      }

      PipelineFailed = {
        Type  = "Fail"
        Error = "PipelineScanError"
        Cause = "ScannerAgent failed; see CloudWatch logs for details"
      }
    }
  })

  tags = merge(var.tags, { Name = "${local.prefix}-pipeline" })
}

# ─────────────────────────────────────────────
# EventBridge Scheduled Rule
# ─────────────────────────────────────────────

data "aws_iam_policy_document" "eventbridge_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eventbridge" {
  name               = "${local.prefix}-eventbridge-pipeline-role"
  assume_role_policy = data.aws_iam_policy_document.eventbridge_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "eventbridge_inline" {
  name = "${local.prefix}-eventbridge-pipeline-policy"
  role = aws_iam_role.eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["states:StartExecution"]
        Resource = aws_sfn_state_machine.pipeline.arn
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "pipeline_schedule" {
  count               = var.enable_schedule ? 1 : 0
  name                = "${local.prefix}-pipeline-schedule"
  description         = "Trigger the Deal Finder pipeline on a schedule"
  schedule_expression = var.schedule_expression
  state               = "ENABLED"
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "pipeline_schedule" {
  count    = var.enable_schedule ? 1 : 0
  rule     = aws_cloudwatch_event_rule.pipeline_schedule[0].name
  arn      = aws_sfn_state_machine.pipeline.arn
  role_arn = aws_iam_role.eventbridge.arn
  input    = jsonencode({})
}

# ─────────────────────────────────────────────
# CloudWatch Alarms — DLQ depth
# ─────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "deal_processing_dlq" {
  count               = var.alarm_sns_topic_arn != "" ? 1 : 0
  alarm_name          = "${local.prefix}-deal-processing-dlq-depth"
  alarm_description   = "Messages in deal-processing DLQ — indicates pipeline failures"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.deal_processing_dlq.name }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alarm_sns_topic_arn]
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "notification_dispatch_dlq" {
  count               = var.alarm_sns_topic_arn != "" ? 1 : 0
  alarm_name          = "${local.prefix}-notification-dispatch-dlq-depth"
  alarm_description   = "Messages in notification-dispatch DLQ — indicates dispatch failures"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.notification_dispatch_dlq.name }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alarm_sns_topic_arn]
  tags                = var.tags
}
