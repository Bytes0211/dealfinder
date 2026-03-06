# Deal State Table (with TTL for short-lived data)
resource "aws_dynamodb_table" "deal_state" {
  name         = "${var.project_name}-${var.environment}-deal-state"
  billing_mode = "PAY_PER_REQUEST" # On-demand pricing for variable traffic

  hash_key  = "deal_id"
  range_key = "timestamp"

  attribute {
    name = "deal_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  ttl {
    attribute_name = "expiration_time"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-deal-state"
      Purpose    = "deal-cache"
      Persistent = "false" # Data expires automatically via TTL
    }
  )
}

# Agent Execution State Table
resource "aws_dynamodb_table" "agent_state" {
  name         = "${var.project_name}-${var.environment}-agent-state"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "execution_id"
  range_key = "agent_name"

  attribute {
    name = "execution_id"
    type = "S"
  }

  attribute {
    name = "agent_name"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-agent-state"
      Purpose    = "orchestration"
      Persistent = "true"
    }
  )
}

# User Sessions Table
resource "aws_dynamodb_table" "user_sessions" {
  name         = "${var.project_name}-${var.environment}-user-sessions"
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  ttl {
    attribute_name = "expiration_time"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = false # Sessions are ephemeral
  }

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-user-sessions"
      Purpose    = "session-management"
      Persistent = "false"
    }
  )
}
