output "scanner_function_arn" {
  description = "ARN of the Scanner Lambda function"
  value       = aws_lambda_function.scanner.arn
}

output "scanner_function_name" {
  description = "Name of the Scanner Lambda function"
  value       = aws_lambda_function.scanner.function_name
}

output "evaluator_function_arn" {
  description = "ARN of the Evaluator Lambda function"
  value       = aws_lambda_function.evaluator.arn
}

output "evaluator_function_name" {
  description = "Name of the Evaluator Lambda function"
  value       = aws_lambda_function.evaluator.function_name
}

output "state_machine_arn" {
  description = "ARN of the Step Functions pipeline state machine"
  value       = aws_sfn_state_machine.pipeline.arn
}

output "state_machine_name" {
  description = "Name of the Step Functions pipeline state machine"
  value       = aws_sfn_state_machine.pipeline.name
}

output "deal_processing_queue_url" {
  description = "URL of the deal-processing SQS queue"
  value       = aws_sqs_queue.deal_processing.url
}

output "deal_processing_queue_arn" {
  description = "ARN of the deal-processing SQS queue"
  value       = aws_sqs_queue.deal_processing.arn
}

output "deal_processing_dlq_url" {
  description = "URL of the deal-processing dead-letter queue"
  value       = aws_sqs_queue.deal_processing_dlq.url
}

output "notification_dispatch_queue_url" {
  description = "URL of the notification-dispatch SQS queue"
  value       = aws_sqs_queue.notification_dispatch.url
}

output "notification_dispatch_queue_arn" {
  description = "ARN of the notification-dispatch SQS queue"
  value       = aws_sqs_queue.notification_dispatch.arn
}

output "notification_dispatch_dlq_url" {
  description = "URL of the notification-dispatch dead-letter queue"
  value       = aws_sqs_queue.notification_dispatch_dlq.url
}

output "lambda_security_group_id" {
  description = "Security group ID attached to pipeline Lambda functions"
  value       = aws_security_group.lambda.id
}
