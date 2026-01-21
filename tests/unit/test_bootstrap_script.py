"""
Unit tests for Terraform bootstrap script.

Tests that the bootstrap script correctly sets up S3 backend and DynamoDB
state locking with proper configuration including lifecycle policies.
"""

import re
from pathlib import Path


class TestBootstrapScript:
    """Test bootstrap script configuration."""

    @classmethod
    def setup_class(cls):
        """Load bootstrap script."""
        cls.script_file = Path(__file__).parent.parent.parent / "infrastructure" / "bootstrap.sh"
        cls.script_content = cls.script_file.read_text()

    def test_bootstrap_script_exists(self):
        """Test that bootstrap script exists."""
        assert self.script_file.exists(), \
            "Bootstrap script should exist"

    def test_shebang_present(self):
        """Test that script has proper shebang."""
        assert self.script_content.startswith("#!/bin/bash"), \
            "Script should start with bash shebang"

    def test_script_has_error_handling(self):
        """Test that script uses set -e for error handling."""
        assert "set -e" in self.script_content, \
            "Script should use 'set -e' for error handling"

    def test_script_parameters(self):
        """Test that script accepts region and environment parameters."""
        assert 'REGION="${1:-us-east-1}"' in self.script_content, \
            "Script should accept region parameter with default"
        assert 'ENVIRONMENT="${2:-dev}"' in self.script_content, \
            "Script should accept environment parameter with default"

    def test_project_name_variable(self):
        """Test that project name is set correctly."""
        assert 'PROJECT_NAME="dealfinder"' in self.script_content, \
            "Project name should be set to dealfinder"

    def test_bucket_naming(self):
        """Test that S3 bucket is named correctly."""
        assert 'BUCKET_NAME="${PROJECT_NAME}-terraform-state-${ENVIRONMENT}"' in self.script_content, \
            "Bucket should be named with pattern: project-terraform-state-environment"

    def test_dynamodb_table_naming(self):
        """Test that DynamoDB table is named correctly."""
        assert 'DYNAMODB_TABLE="${PROJECT_NAME}-terraform-locks"' in self.script_content, \
            "DynamoDB table should be named with pattern: project-terraform-locks"

    def test_aws_credentials_check(self):
        """Test that script validates AWS credentials."""
        assert "aws sts get-caller-identity" in self.script_content, \
            "Script should validate AWS credentials using STS"
        assert "&>/dev/null" in self.script_content, \
            "Credential check should suppress output"

    def test_s3_bucket_creation(self):
        """Test that S3 bucket is created with proper configuration."""
        # Check bucket creation
        assert "aws s3api create-bucket" in self.script_content, \
            "Script should create S3 bucket"
        assert '--bucket "${BUCKET_NAME}"' in self.script_content, \
            "Bucket creation should use BUCKET_NAME variable"
        assert '--region "${REGION}"' in self.script_content, \
            "Bucket creation should use REGION variable"

    def test_s3_bucket_existence_check(self):
        """Test that script checks if bucket already exists."""
        assert "aws s3api head-bucket" in self.script_content, \
            "Script should check if bucket already exists"
        assert "already exists" in self.script_content, \
            "Script should handle existing bucket gracefully"

    def test_s3_versioning_enabled(self):
        """Test that S3 versioning is enabled."""
        assert "aws s3api put-bucket-versioning" in self.script_content, \
            "Script should enable bucket versioning"
        assert '"Status": "Enabled"' in self.script_content or \
               "Status=Enabled" in self.script_content, \
            "Versioning status should be Enabled"

    def test_s3_encryption_enabled(self):
        """Test that S3 encryption is enabled."""
        assert "aws s3api put-bucket-encryption" in self.script_content, \
            "Script should enable bucket encryption"
        assert "AES256" in self.script_content, \
            "Encryption should use AES256"
        assert "BucketKeyEnabled" in self.script_content, \
            "Bucket key should be enabled"

    def test_s3_public_access_block(self):
        """Test that public access is blocked."""
        assert "aws s3api put-public-access-block" in self.script_content, \
            "Script should block public access"
        assert "BlockPublicAcls=true" in self.script_content, \
            "Should block public ACLs"
        assert "IgnorePublicAcls=true" in self.script_content, \
            "Should ignore public ACLs"
        assert "BlockPublicPolicy=true" in self.script_content, \
            "Should block public policy"
        assert "RestrictPublicBuckets=true" in self.script_content, \
            "Should restrict public buckets"

    def test_s3_lifecycle_configuration(self):
        """Test that lifecycle configuration is set with correct casing."""
        assert "aws s3api put-bucket-lifecycle-configuration" in self.script_content, \
            "Script should set lifecycle configuration"
        
        # Check for lifecycle configuration JSON structure
        assert '"Rules"' in self.script_content, \
            "Lifecycle configuration should have Rules"

    def test_lifecycle_id_parameter_casing(self):
        """Test that lifecycle configuration uses correct casing for ID parameter."""
        # The ID field should use capital "ID", not "Id"
        assert '"ID":' in self.script_content, \
            "Lifecycle rule should use 'ID' (capital letters)"
        
        # Extract lifecycle configuration section
        lifecycle_start = self.script_content.find("put-bucket-lifecycle-configuration")
        lifecycle_end = self.script_content.find("--no-cli-pager", lifecycle_start + 1)
        lifecycle_section = self.script_content[lifecycle_start:lifecycle_end]
        
        # Verify ID is present in lifecycle section
        assert '"ID"' in lifecycle_section, \
            "Lifecycle configuration should contain ID field with correct casing"
        
        # Verify it's specifically "ID" not "Id"
        assert '"Id"' not in lifecycle_section, \
            "Lifecycle configuration should not use 'Id' (incorrect casing)"

    def test_lifecycle_delete_old_versions(self):
        """Test that lifecycle policy deletes old versions."""
        assert "DeleteOldVersions" in self.script_content, \
            "Lifecycle policy should be named DeleteOldVersions"
        assert "NoncurrentVersionExpiration" in self.script_content, \
            "Lifecycle policy should expire noncurrent versions"
        assert "NoncurrentDays" in self.script_content, \
            "Lifecycle policy should specify noncurrent days"
        assert "90" in self.script_content, \
            "Lifecycle policy should delete after 90 days"

    def test_s3_tagging(self):
        """Test that S3 bucket is tagged properly."""
        assert "aws s3api put-bucket-tagging" in self.script_content, \
            "Script should tag the bucket"
        
        # Check for required tags
        assert "Key=Project,Value=${PROJECT_NAME}" in self.script_content, \
            "Bucket should have Project tag"
        assert "Key=Environment,Value=${ENVIRONMENT}" in self.script_content, \
            "Bucket should have Environment tag"
        assert "Key=ManagedBy,Value=terraform" in self.script_content, \
            "Bucket should have ManagedBy tag"
        assert "Key=Purpose,Value=terraform-state" in self.script_content, \
            "Bucket should have Purpose tag"

    def test_dynamodb_table_creation(self):
        """Test that DynamoDB table is created correctly."""
        assert "aws dynamodb create-table" in self.script_content, \
            "Script should create DynamoDB table"
        assert '--table-name "${DYNAMODB_TABLE}"' in self.script_content, \
            "Table creation should use DYNAMODB_TABLE variable"

    def test_dynamodb_table_existence_check(self):
        """Test that script checks if DynamoDB table already exists."""
        assert "aws dynamodb describe-table" in self.script_content, \
            "Script should check if table already exists"
        assert "already exists" in self.script_content, \
            "Script should handle existing table gracefully"

    def test_dynamodb_lock_id_attribute(self):
        """Test that DynamoDB table has LockID attribute."""
        assert "AttributeName=LockID,AttributeType=S" in self.script_content, \
            "Table should have LockID string attribute"
        assert "AttributeName=LockID,KeyType=HASH" in self.script_content, \
            "LockID should be the hash key"

    def test_dynamodb_billing_mode(self):
        """Test that DynamoDB uses pay-per-request billing."""
        assert "--billing-mode PAY_PER_REQUEST" in self.script_content, \
            "Table should use PAY_PER_REQUEST billing mode"

    def test_dynamodb_tagging(self):
        """Test that DynamoDB table is tagged properly."""
        # Check for required tags in DynamoDB creation
        assert 'Key=Project,Value="${PROJECT_NAME}"' in self.script_content, \
            "DynamoDB table should have Project tag"
        assert 'Key=Environment,Value="${ENVIRONMENT}"' in self.script_content, \
            "DynamoDB table should have Environment tag"
        assert "Key=ManagedBy,Value=terraform" in self.script_content, \
            "DynamoDB table should have ManagedBy tag"
        assert "Key=Purpose,Value=terraform-state-lock" in self.script_content, \
            "DynamoDB table should have Purpose tag"

    def test_dynamodb_wait_for_active(self):
        """Test that script waits for table to become active."""
        assert "aws dynamodb wait table-exists" in self.script_content, \
            "Script should wait for table to become active"

    def test_backend_configuration_output(self):
        """Test that script outputs backend configuration."""
        assert 'terraform {' in self.script_content, \
            "Script should output terraform backend configuration"
        assert 'backend "s3"' in self.script_content, \
            "Backend configuration should use S3"
        assert 'bucket         = "${BUCKET_NAME}"' in self.script_content, \
            "Backend config should include bucket name"
        assert 'key            = "terraform.tfstate"' in self.script_content, \
            "Backend config should include state key"
        assert 'region         = "${REGION}"' in self.script_content, \
            "Backend config should include region"
        assert 'encrypt        = true' in self.script_content, \
            "Backend config should enable encryption"
        assert 'dynamodb_table = "${DYNAMODB_TABLE}"' in self.script_content, \
            "Backend config should include DynamoDB table"

    def test_no_cli_pager_flag(self):
        """Test that AWS CLI commands disable pager."""
        # Count aws commands and --no-cli-pager flags
        aws_commands = self.script_content.count("aws s3api") + \
                      self.script_content.count("aws dynamodb create-table")
        no_pager_flags = self.script_content.count("--no-cli-pager")
        
        assert no_pager_flags > 0, \
            "AWS CLI commands should use --no-cli-pager flag"

    def test_success_message(self):
        """Test that script outputs success message."""
        assert "Bootstrap Complete" in self.script_content, \
            "Script should output success message"
        assert "✓" in self.script_content, \
            "Script should use checkmarks for success indicators"

    def test_informational_output(self):
        """Test that script provides informational output."""
        assert "Project:" in self.script_content, \
            "Script should display project name"
        assert "Region:" in self.script_content, \
            "Script should display region"
        assert "Environment:" in self.script_content, \
            "Script should display environment"
        assert "S3 Bucket:" in self.script_content, \
            "Script should display S3 bucket name"
        assert "DynamoDB Table:" in self.script_content, \
            "Script should display DynamoDB table name"

    def test_usage_documentation(self):
        """Test that script includes usage documentation."""
        # Check for usage comments at the top of the file
        first_100_lines = '\n'.join(self.script_content.split('\n')[:20])
        
        assert "Usage:" in first_100_lines, \
            "Script should include usage documentation"
        assert "Example:" in first_100_lines or \
               "bootstrap.sh" in first_100_lines, \
            "Script should include usage example"

    def test_region_conditional_logic(self):
        """Test that script handles us-east-1 region specially for bucket creation."""
        # S3 create-bucket has special handling for us-east-1
        # (no LocationConstraint needed)
        assert "us-east-1" in self.script_content, \
            "Script should have special handling for us-east-1"
        assert "LocationConstraint" in self.script_content, \
            "Script should set LocationConstraint for non-us-east-1 regions"
