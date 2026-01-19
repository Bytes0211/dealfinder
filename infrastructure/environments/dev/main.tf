terraform {
  required_version = ">= 1.14"

  backend "s3" {
    bucket         = "dealfinder-terraform-state-dev"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "dealfinder-terraform-locks"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Networking Module
module "networking" {
  source = "../../modules/networking"

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_cidr           = var.vpc_cidr
  enable_nat_gateway = var.enable_nat_gateway

  tags = local.common_tags
}

# S3 Storage Module
module "s3" {
  source = "../../modules/data/s3"

  project_name = var.project_name
  environment  = var.environment

  tags = local.common_tags
}

# DynamoDB Module
module "dynamodb" {
  source = "../../modules/data/dynamodb"

  project_name = var.project_name
  environment  = var.environment

  tags = local.common_tags
}

# TODO: Add additional modules as they are implemented
# module "msk" {
#   source = "../../modules/data/msk"
#   count  = var.enable_msk ? 1 : 0
#   ...
# }

# module "opensearch" {
#   source = "../../modules/data/opensearch"
#   count  = var.enable_opensearch ? 1 : 0
#   ...
# }

# module "ecs" {
#   source = "../../modules/compute/ecs"
#   count  = var.enable_ecs ? 1 : 0
#   ...
# }
