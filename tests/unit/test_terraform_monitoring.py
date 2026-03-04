"""
Unit tests for Terraform monitoring module configuration.

Tests that the CloudWatch monitoring module variables are correctly configured
with log retention and alarm email variables.
"""

import json
import re
from pathlib import Path


class TestTerraformMonitoringModule:
    """Test Terraform monitoring module configuration."""

    @classmethod
    def setup_class(cls):
        """Load Terraform module files."""
        cls.module_path = Path(__file__).parent.parent.parent / "infrastructure" / "modules" / "monitoring" / "cloudwatch"
        cls.variables_tf = cls.module_path / "variables.tf"
        cls.main_tf = cls.module_path / "main.tf"

    def test_variables_file_exists(self):
        """Test that variables.tf exists."""
        assert self.variables_tf.exists(), "variables.tf should exist in monitoring module"

    def test_main_file_exists(self):
        """Test that main.tf exists."""
        assert self.main_tf.exists(), "main.tf should exist in monitoring module"

    def test_log_retention_variable_defined(self):
        """Test that log_retention_days variable is defined."""
        content = self.variables_tf.read_text()
        
        # Check variable exists
        assert 'variable "log_retention_days"' in content, \
            "log_retention_days variable should be defined"
        
        # Extract variable block
        pattern = r'variable "log_retention_days"\s*{[^}]+}'
        match = re.search(pattern, content, re.DOTALL)
        assert match is not None, "log_retention_days variable block should be complete"
        
        var_block = match.group(0)
        
        # Check type
        assert 'type        = number' in var_block or 'type = number' in var_block, \
            "log_retention_days should have type number"
        
        # Check description
        assert 'description' in var_block, \
            "log_retention_days should have a description"
        
        # Check default value
        assert 'default' in var_block, \
            "log_retention_days should have a default value"
        assert '30' in var_block, \
            "log_retention_days default should be 30"

    def test_alarm_email_variable_defined(self):
        """Test that alarm_email variable is defined."""
        content = self.variables_tf.read_text()
        
        # Check variable exists
        assert 'variable "alarm_email"' in content, \
            "alarm_email variable should be defined"
        
        # Extract variable block
        pattern = r'variable "alarm_email"\s*{[^}]+}'
        match = re.search(pattern, content, re.DOTALL)
        assert match is not None, "alarm_email variable block should be complete"
        
        var_block = match.group(0)
        
        # Check type
        assert 'type        = string' in var_block or 'type = string' in var_block, \
            "alarm_email should have type string"
        
        # Check description
        assert 'description' in var_block, \
            "alarm_email should have a description"
        
        # Check default value
        assert 'default' in var_block, \
            "alarm_email should have a default value"
        assert '""' in var_block, \
            "alarm_email default should be empty string"

    def test_required_variables_defined(self):
        """Test that all required variables are defined."""
        content = self.variables_tf.read_text()
        
        required_vars = [
            "project_name",
            "environment",
            "aws_region",
            "log_retention_days",
            "alarm_email",
            "tags"
        ]
        
        for var in required_vars:
            assert f'variable "{var}"' in content, \
                f"{var} variable should be defined"

    def test_log_groups_use_retention_variable(self):
        """Test that log groups use the log_retention_days variable."""
        content = self.main_tf.read_text()
        
        # Check that retention_in_days is set to the variable
        # Using a simpler approach - just count occurrences
        retention_uses = content.count("retention_in_days = var.log_retention_days")
        
        assert retention_uses >= 3, \
            f"Should have at least 3 log groups using var.log_retention_days, found {retention_uses}"

    def test_sns_topic_subscription_uses_alarm_email(self):
        """Test that SNS topic subscription uses alarm_email variable."""
        content = self.main_tf.read_text()
        
        # Check SNS topic subscription resource
        assert 'resource "aws_sns_topic_subscription" "alarms_email"' in content, \
            "SNS topic subscription for alarms should exist"
        
        # Extract subscription block
        pattern = r'resource "aws_sns_topic_subscription" "alarms_email"\s*{[^}]+}'
        match = re.search(pattern, content, re.DOTALL)
        assert match is not None, "SNS subscription block should be complete"
        
        subscription_block = match.group(0)
        
        # Check conditional count
        assert 'count     = var.alarm_email != "" ? 1 : 0' in subscription_block or \
               'count = var.alarm_email != "" ? 1 : 0' in subscription_block, \
            "SNS subscription should be conditional on alarm_email being non-empty"
        
        # Check endpoint uses variable
        assert 'endpoint  = var.alarm_email' in subscription_block or \
               'endpoint = var.alarm_email' in subscription_block, \
            "SNS subscription endpoint should use var.alarm_email"

    def test_sns_topic_exists(self):
        """Test that SNS topic for alarms is defined."""
        content = self.main_tf.read_text()
        
        assert 'resource "aws_sns_topic" "alarms"' in content, \
            "SNS topic for alarms should be defined"

    def test_cloudwatch_alarms_use_sns_topic(self):
        """Test that CloudWatch alarms use the SNS topic."""
        content = self.main_tf.read_text()
        
        # Count CloudWatch alarm resources
        alarm_count = content.count('resource "aws_cloudwatch_metric_alarm"')
        
        assert alarm_count >= 5, \
            f"Should have at least 5 CloudWatch alarms, found {alarm_count}"
        
        # Check that alarms reference the SNS topic
        sns_topic_refs = content.count("aws_sns_topic.alarms.arn")
        assert sns_topic_refs >= 5, \
            f"All alarms should reference SNS topic ARN, found {sns_topic_refs} references"

    def test_cost_anomaly_subscription_uses_alarm_email(self):
        """Test that cost anomaly subscription uses alarm_email variable."""
        content = self.main_tf.read_text()
        
        # Check cost anomaly subscription resource
        assert 'resource "aws_ce_anomaly_subscription" "dealfinder"' in content, \
            "Cost anomaly subscription should exist"
        
        # Check subscriber uses alarm_email - simpler approach
        # The subscription block has an address field that uses the variable
        assert "address = var.alarm_email" in content or \
               'address = "' in content and 'var.alarm_email' in content, \
            "Cost anomaly subscription should use var.alarm_email"

    def test_log_group_naming_convention(self):
        """Test that log groups follow AWS naming conventions."""
        content = self.main_tf.read_text()
        
        expected_log_groups = [
            '"/aws/dealfinder/${var.environment}/application"',
            '"/aws/lambda/${var.project_name}-${var.environment}"',
            '"/aws/ecs/${var.project_name}-${var.environment}"'
        ]
        
        for expected in expected_log_groups:
            assert expected in content, \
                f"Log group {expected} should be defined"

    def test_cloudwatch_dashboard_exists(self):
        """Test that CloudWatch dashboard is defined."""
        content = self.main_tf.read_text()
        
        assert 'resource "aws_cloudwatch_dashboard" "main"' in content, \
            "CloudWatch dashboard should be defined"
        
        # Check dashboard uses jsonencode
        assert "dashboard_body = jsonencode" in content, \
            "Dashboard body should use jsonencode"

    def test_tags_variable_defined(self):
        """Test that tags variable is defined correctly."""
        content = self.variables_tf.read_text()
        
        # Extract tags variable block
        pattern = r'variable "tags"\s*{[^}]+}'
        match = re.search(pattern, content, re.DOTALL)
        assert match is not None, "tags variable should be defined"
        
        var_block = match.group(0)
        
        # Check type
        assert 'type        = map(string)' in var_block or 'type = map(string)' in var_block, \
            "tags should have type map(string)"
        
        # Check default
        assert 'default     = {}' in var_block or 'default = {}' in var_block, \
            "tags should have default empty map"
