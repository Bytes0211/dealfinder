#!/bin/bash
# Terraform Backend Bootstrap Script
# Creates S3 bucket and DynamoDB table for Terraform state management
#
# Usage: ./bootstrap.sh [region] [environment]
# Example: ./bootstrap.sh us-east-1 dev

set -e

REGION="${1:-us-east-1}"
ENVIRONMENT="${2:-dev}"
PROJECT_NAME="dealfinder"
BUCKET_NAME="${PROJECT_NAME}-terraform-state-${ENVIRONMENT}"
DYNAMODB_TABLE="${PROJECT_NAME}-terraform-locks"

echo "================================================"
echo "Terraform Backend Bootstrap"
echo "================================================"
echo "Project: ${PROJECT_NAME}"
echo "Region: ${REGION}"
echo "Environment: ${ENVIRONMENT}"
echo "S3 Bucket: ${BUCKET_NAME}"
echo "DynamoDB Table: ${DYNAMODB_TABLE}"
echo "================================================"
echo ""

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &>/dev/null; then
    echo "❌ Error: AWS CLI not configured or no valid credentials"
    echo "Run 'aws configure' to set up your credentials"
    exit 1
fi

echo "✓ AWS credentials validated"
echo ""

# Create S3 bucket for Terraform state
echo "Creating S3 bucket: ${BUCKET_NAME}..."
if aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
    echo "⚠️  S3 bucket already exists: ${BUCKET_NAME}"
else
    aws s3api create-bucket \
        --bucket "${BUCKET_NAME}" \
        --region "${REGION}" \
        $(if [ "${REGION}" != "us-east-1" ]; then echo "--create-bucket-configuration LocationConstraint=${REGION}"; fi) \
        --no-cli-pager

    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "${BUCKET_NAME}" \
        --versioning-configuration Status=Enabled \
        --no-cli-pager

    # Enable encryption
    aws s3api put-bucket-encryption \
        --bucket "${BUCKET_NAME}" \
        --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                },
                "BucketKeyEnabled": true
            }]
        }' \
        --no-cli-pager

    # Block public access
    aws s3api put-public-access-block \
        --bucket "${BUCKET_NAME}" \
        --public-access-block-configuration \
            BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true \
        --no-cli-pager

    # Add lifecycle policy to manage old state versions
    aws s3api put-bucket-lifecycle-configuration \
        --bucket "${BUCKET_NAME}" \
        --lifecycle-configuration '{
            "Rules": [{
                "ID": "DeleteOldVersions",
                "Status": "Enabled",
                "NoncurrentVersionExpiration": {
                    "NoncurrentDays": 90
                }
            }]
        }' \
        --no-cli-pager

    # Add tags
    aws s3api put-bucket-tagging \
        --bucket "${BUCKET_NAME}" \
        --tagging "TagSet=[
            {Key=Project,Value=${PROJECT_NAME}},
            {Key=Environment,Value=${ENVIRONMENT}},
            {Key=ManagedBy,Value=terraform},
            {Key=Purpose,Value=terraform-state}
        ]" \
        --no-cli-pager

    echo "✓ S3 bucket created and configured: ${BUCKET_NAME}"
fi

echo ""

# Create DynamoDB table for state locking
echo "Creating DynamoDB table: ${DYNAMODB_TABLE}..."
if aws dynamodb describe-table --table-name "${DYNAMODB_TABLE}" --region "${REGION}" &>/dev/null; then
    echo "⚠️  DynamoDB table already exists: ${DYNAMODB_TABLE}"
else
    aws dynamodb create-table \
        --table-name "${DYNAMODB_TABLE}" \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region "${REGION}" \
        --tags Key=Project,Value="${PROJECT_NAME}" \
              Key=Environment,Value="${ENVIRONMENT}" \
              Key=ManagedBy,Value=terraform \
              Key=Purpose,Value=terraform-state-lock \
        --no-cli-pager

    echo "Waiting for table to become active..."
    aws dynamodb wait table-exists \
        --table-name "${DYNAMODB_TABLE}" \
        --region "${REGION}"

    echo "✓ DynamoDB table created: ${DYNAMODB_TABLE}"
fi

echo ""
echo "================================================"
echo "✓ Bootstrap Complete!"
echo "================================================"
echo ""
echo "Add this backend configuration to your Terraform:"
echo ""
cat <<EOF
terraform {
  backend "s3" {
    bucket         = "${BUCKET_NAME}"
    key            = "terraform.tfstate"
    region         = "${REGION}"
    encrypt        = true
    dynamodb_table = "${DYNAMODB_TABLE}"
  }
}
EOF
echo ""
echo "================================================"
