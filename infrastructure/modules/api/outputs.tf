output "api_function_arn" {
  description = "ARN of the API Lambda function"
  value       = aws_lambda_function.api.arn
}

output "api_function_name" {
  description = "Name of the API Lambda function"
  value       = aws_lambda_function.api.function_name
}

output "api_endpoint" {
  description = "Base URL of the API Gateway HTTP API"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "api_gateway_id" {
  description = "ID of the API Gateway HTTP API"
  value       = aws_apigatewayv2_api.main.id
}

output "cognito_user_pool_id" {
  description = "ID of the Cognito user pool"
  value       = aws_cognito_user_pool.main.id
}

output "cognito_user_pool_arn" {
  description = "ARN of the Cognito user pool"
  value       = aws_cognito_user_pool.main.arn
}

output "cognito_user_pool_endpoint" {
  description = "Endpoint of the Cognito user pool"
  value       = aws_cognito_user_pool.main.endpoint
}

output "cognito_client_id" {
  description = "ID of the Cognito user pool client for the API"
  value       = aws_cognito_user_pool_client.api.id
}

output "cognito_hosted_ui_domain" {
  description = "Cognito Hosted UI base domain (e.g. dealfinder-prod.auth.us-east-1.amazoncognito.com)"
  value       = var.cognito_domain_prefix != "" ? "${var.cognito_domain_prefix}.auth.${var.aws_region}.amazoncognito.com" : null
}
