terraform {
  required_version = ">= 1.14"

  backend "s3" {
    bucket       = "dealfinder-terraform-state-prod"
    key          = "oidc/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# ── GitHub Actions OIDC Provider ─────────────────────────────────────────────

resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  # GitHub's OIDC thumbprint (stable — managed by GitHub)
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = {
    Project   = "dealfinder"
    ManagedBy = "terraform"
  }
}

# ── Deploy IAM Role ───────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "github_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Allow main branch pushes and jobs using the 'production' environment
    # (environment: production in a job changes the sub to :environment:production)
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:Bytes0211/dealfinder:ref:refs/heads/main",
        "repo:Bytes0211/dealfinder:environment:production",
      ]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "dealfinder-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_assume_role.json
  description        = "Role assumed by GitHub Actions to deploy the Deal Finder frontend"

  tags = {
    Project   = "dealfinder"
    ManagedBy = "terraform"
  }
}

# ── Deploy Policy (S3 + CloudFront) ──────────────────────────────────────────

data "aws_iam_policy_document" "deploy" {
  statement {
    sid    = "S3FrontendDeploy"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      "arn:aws:s3:::dealfinder-frontend-prod*",
      "arn:aws:s3:::dealfinder-frontend-prod*/*",
    ]
  }

  statement {
    sid    = "CloudFrontInvalidate"
    effect = "Allow"
    actions = [
      "cloudfront:CreateInvalidation",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "dealfinder-github-deploy-policy"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}

# ── Output ────────────────────────────────────────────────────────────────────

output "deploy_role_arn" {
  description = "ARN of the GitHub Actions deploy role — use as AWS_DEPLOY_ROLE_ARN secret"
  value       = aws_iam_role.github_deploy.arn
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider"
  value       = aws_iam_openid_connect_provider.github.arn
}
