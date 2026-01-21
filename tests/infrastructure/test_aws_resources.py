"""
Infrastructure validation tests for Deal Finder AWS resources.

These tests validate that the infrastructure deployed in Phase 1 is operational
and configured correctly.
"""

import boto3
import pytest
from botocore.exceptions import ClientError


@pytest.fixture(scope="module")
def aws_region():
    """AWS region for testing."""
    return "us-east-1"


@pytest.fixture(scope="module")
def project_name():
    """Project name for resource naming."""
    return "dealfinder"


@pytest.fixture(scope="module")
def environment():
    """Environment name."""
    return "dev"


@pytest.fixture(scope="module")
def ec2_client(aws_region):
    """EC2 client for VPC testing."""
    return boto3.client("ec2", region_name=aws_region)


@pytest.fixture(scope="module")
def s3_client(aws_region):
    """S3 client for bucket testing."""
    return boto3.client("s3", region_name=aws_region)


@pytest.fixture(scope="module")
def dynamodb_client(aws_region):
    """DynamoDB client for table testing."""
    return boto3.client("dynamodb", region_name=aws_region)


@pytest.fixture(scope="module")
def cloudwatch_client(aws_region):
    """CloudWatch client for monitoring testing."""
    return boto3.client("cloudwatch", region_name=aws_region)


@pytest.fixture(scope="module")
def sns_client(aws_region):
    """SNS client for alarms testing."""
    return boto3.client("sns", region_name=aws_region)


class TestVPCNetworking:
    """Test VPC and networking infrastructure."""

    def test_vpc_exists(self, ec2_client, project_name, environment):
        """Test that VPC exists with correct tags."""
        response = ec2_client.describe_vpcs(
            Filters=[
                {"Name": "tag:Project", "Values": [project_name]},
                {"Name": "tag:Environment", "Values": [environment]},
            ]
        )
        assert len(response["Vpcs"]) == 1, "VPC should exist"
        vpc = response["Vpcs"][0]
        assert vpc["CidrBlock"] == "10.0.0.0/16", "VPC CIDR should be 10.0.0.0/16"

    def test_subnets_exist(self, ec2_client, project_name, environment):
        """Test that all subnets exist (3 public + 3 private)."""
        response = ec2_client.describe_subnets(
            Filters=[
                {"Name": "tag:Project", "Values": [project_name]},
                {"Name": "tag:Environment", "Values": [environment]},
            ]
        )
        assert len(response["Subnets"]) == 6, "Should have 6 subnets"

        # Check availability zones
        azs = {subnet["AvailabilityZone"] for subnet in response["Subnets"]}
        assert len(azs) == 3, "Subnets should span 3 availability zones"

    def test_internet_gateway_exists(self, ec2_client, project_name, environment):
        """Test that Internet Gateway exists."""
        response = ec2_client.describe_internet_gateways(
            Filters=[
                {"Name": "tag:Project", "Values": [project_name]},
                {"Name": "tag:Environment", "Values": [environment]},
            ]
        )
        assert len(response["InternetGateways"]) == 1, "Internet Gateway should exist"

    def test_vpc_endpoints_exist(self, ec2_client):
        """Test that VPC endpoints for S3 and DynamoDB exist."""
        response = ec2_client.describe_vpc_endpoints()
        
        service_names = {ep["ServiceName"] for ep in response["VpcEndpoints"]}
        
        # Check for S3 and DynamoDB endpoints
        s3_endpoint = any("s3" in sn for sn in service_names)
        dynamodb_endpoint = any("dynamodb" in sn for sn in service_names)
        
        assert s3_endpoint, "S3 VPC endpoint should exist"
        assert dynamodb_endpoint, "DynamoDB VPC endpoint should exist"


class TestS3Storage:
    """Test S3 bucket configuration."""

    def test_data_lake_bucket_exists(self, s3_client, project_name, environment):
        """Test that data lake bucket exists."""
        bucket_name = f"{project_name}-{environment}-data-lake"
        try:
            response = s3_client.head_bucket(Bucket=bucket_name)
            assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
        except ClientError:
            pytest.fail(f"Data lake bucket {bucket_name} does not exist")

    def test_models_bucket_exists(self, s3_client, project_name, environment):
        """Test that models bucket exists."""
        bucket_name = f"{project_name}-{environment}-models"
        try:
            response = s3_client.head_bucket(Bucket=bucket_name)
            assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
        except ClientError:
            pytest.fail(f"Models bucket {bucket_name} does not exist")

    def test_backups_bucket_exists(self, s3_client, project_name, environment):
        """Test that backups bucket exists."""
        bucket_name = f"{project_name}-{environment}-backups"
        try:
            response = s3_client.head_bucket(Bucket=bucket_name)
            assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
        except ClientError:
            pytest.fail(f"Backups bucket {bucket_name} does not exist")

    def test_bucket_encryption(self, s3_client, project_name, environment):
        """Test that buckets have encryption enabled."""
        buckets = [
            f"{project_name}-{environment}-data-lake",
            f"{project_name}-{environment}-models",
            f"{project_name}-{environment}-backups",
        ]
        
        for bucket_name in buckets:
            try:
                response = s3_client.get_bucket_encryption(Bucket=bucket_name)
                rules = response["ServerSideEncryptionConfiguration"]["Rules"]
                assert len(rules) > 0, f"Bucket {bucket_name} should have encryption rules"
                assert rules[0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256"
            except ClientError as e:
                pytest.fail(f"Bucket {bucket_name} encryption check failed: {e}")

    def test_bucket_versioning(self, s3_client, project_name, environment):
        """Test that buckets have versioning enabled."""
        buckets = [
            f"{project_name}-{environment}-data-lake",
            f"{project_name}-{environment}-models",
            f"{project_name}-{environment}-backups",
        ]
        
        for bucket_name in buckets:
            try:
                response = s3_client.get_bucket_versioning(Bucket=bucket_name)
                assert response.get("Status") == "Enabled", f"Bucket {bucket_name} should have versioning enabled"
            except ClientError as e:
                pytest.fail(f"Bucket {bucket_name} versioning check failed: {e}")


class TestDynamoDB:
    """Test DynamoDB table configuration."""

    def test_deal_state_table_exists(self, dynamodb_client, project_name, environment):
        """Test that deal state table exists."""
        table_name = f"{project_name}-{environment}-deal-state"
        try:
            response = dynamodb_client.describe_table(TableName=table_name)
            assert response["Table"]["TableStatus"] == "ACTIVE"
            assert response["Table"]["BillingModeSummary"]["BillingMode"] == "PAY_PER_REQUEST"
        except ClientError:
            pytest.fail(f"Table {table_name} does not exist")

    def test_agent_state_table_exists(self, dynamodb_client, project_name, environment):
        """Test that agent state table exists."""
        table_name = f"{project_name}-{environment}-agent-state"
        try:
            response = dynamodb_client.describe_table(TableName=table_name)
            assert response["Table"]["TableStatus"] == "ACTIVE"
            assert response["Table"]["BillingModeSummary"]["BillingMode"] == "PAY_PER_REQUEST"
        except ClientError:
            pytest.fail(f"Table {table_name} does not exist")

    def test_user_sessions_table_exists(self, dynamodb_client, project_name, environment):
        """Test that user sessions table exists."""
        table_name = f"{project_name}-{environment}-user-sessions"
        try:
            response = dynamodb_client.describe_table(TableName=table_name)
            assert response["Table"]["TableStatus"] == "ACTIVE"
            assert response["Table"]["BillingModeSummary"]["BillingMode"] == "PAY_PER_REQUEST"
        except ClientError:
            pytest.fail(f"Table {table_name} does not exist")

    def test_tables_have_encryption(self, dynamodb_client, project_name, environment):
        """Test that DynamoDB tables have encryption enabled."""
        tables = [
            f"{project_name}-{environment}-deal-state",
            f"{project_name}-{environment}-agent-state",
            f"{project_name}-{environment}-user-sessions",
        ]
        
        for table_name in tables:
            try:
                response = dynamodb_client.describe_table(TableName=table_name)
                sse_description = response["Table"].get("SSEDescription", {})
                assert sse_description.get("Status") in ["ENABLED", "ENABLING"], \
                    f"Table {table_name} should have encryption enabled"
            except ClientError as e:
                pytest.fail(f"Table {table_name} encryption check failed: {e}")


class TestCloudWatchMonitoring:
    """Test CloudWatch monitoring configuration."""

    def test_log_groups_exist(self, cloudwatch_client, project_name, environment):
        """Test that CloudWatch log groups exist."""
        logs_client = boto3.client("logs", region_name="us-east-1")
        
        expected_log_groups = [
            f"/aws/dealfinder/{environment}/application",
            f"/aws/lambda/{project_name}-{environment}",
            f"/aws/ecs/{project_name}-{environment}",
        ]
        
        for log_group_name in expected_log_groups:
            try:
                response = logs_client.describe_log_groups(
                    logGroupNamePrefix=log_group_name
                )
                assert len(response["logGroups"]) > 0, f"Log group {log_group_name} should exist"
            except ClientError as e:
                pytest.fail(f"Log group {log_group_name} check failed: {e}")

    def test_alarms_exist(self, cloudwatch_client, project_name, environment):
        """Test that CloudWatch alarms exist."""
        response = cloudwatch_client.describe_alarms(
            AlarmNamePrefix=f"{project_name}-{environment}"
        )
        
        assert len(response["MetricAlarms"]) >= 5, "Should have at least 5 CloudWatch alarms"
        
        alarm_names = {alarm["AlarmName"] for alarm in response["MetricAlarms"]}
        
        # Check for specific alarms
        expected_alarms = [
            "dynamodb-high-read-capacity",
            "dynamodb-high-write-capacity",
            "lambda-errors",
            "lambda-throttles",
            "s3-storage-size",
        ]
        
        for expected_alarm in expected_alarms:
            assert any(expected_alarm in name for name in alarm_names), \
                f"Alarm containing '{expected_alarm}' should exist"

    def test_sns_topic_exists(self, sns_client, project_name, environment):
        """Test that SNS topic for alarms exists."""
        topic_name = f"{project_name}-{environment}-alarms"
        
        response = sns_client.list_topics()
        topic_arns = [topic["TopicArn"] for topic in response["Topics"]]
        
        assert any(topic_name in arn for arn in topic_arns), \
            f"SNS topic {topic_name} should exist"

    def test_dashboard_exists(self, cloudwatch_client, project_name, environment):
        """Test that CloudWatch dashboard exists."""
        dashboard_name = f"{project_name}-{environment}-dashboard"
        
        try:
            response = cloudwatch_client.get_dashboard(DashboardName=dashboard_name)
            assert response["DashboardName"] == dashboard_name
        except ClientError:
            pytest.fail(f"Dashboard {dashboard_name} does not exist")


class TestCostManagement:
    """Test cost management configuration."""

    def test_cost_anomaly_monitor_exists(self):
        """Test that cost anomaly monitor exists."""
        ce_client = boto3.client("ce", region_name="us-east-1")
        
        try:
            response = ce_client.get_anomaly_monitors()
            monitors = response.get("AnomalyMonitors", [])
            
            # Check if any monitor exists for the project
            project_monitors = [
                m for m in monitors 
                if "dealfinder" in m.get("MonitorName", "").lower()
            ]
            
            assert len(project_monitors) > 0, "Cost anomaly monitor should exist"
        except ClientError as e:
            # Cost Explorer may not be available in all accounts
            pytest.skip(f"Cost Explorer not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
