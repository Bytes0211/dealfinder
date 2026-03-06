output "deal_state_table_name" {
  description = "Deal state table name"
  value       = aws_dynamodb_table.deal_state.name
}

output "deal_state_table_arn" {
  description = "Deal state table ARN"
  value       = aws_dynamodb_table.deal_state.arn
}

output "agent_state_table_name" {
  description = "Agent state table name"
  value       = aws_dynamodb_table.agent_state.name
}

output "agent_state_table_arn" {
  description = "Agent state table ARN"
  value       = aws_dynamodb_table.agent_state.arn
}

output "user_sessions_table_name" {
  description = "User sessions table name"
  value       = aws_dynamodb_table.user_sessions.name
}

output "user_sessions_table_arn" {
  description = "User sessions table ARN"
  value       = aws_dynamodb_table.user_sessions.arn
}
