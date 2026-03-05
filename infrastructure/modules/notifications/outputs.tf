output "sns_topic_arn" {
  description = "ARN of the deal-notifications SNS topic"
  value       = aws_sns_topic.deal_notifications.arn
}

output "sns_topic_name" {
  description = "Name of the deal-notifications SNS topic"
  value       = aws_sns_topic.deal_notifications.name
}

output "messenger_function_arn" {
  description = "ARN of the Messenger Lambda function"
  value       = aws_lambda_function.messenger.arn
}

output "messenger_function_name" {
  description = "Name of the Messenger Lambda function"
  value       = aws_lambda_function.messenger.function_name
}
