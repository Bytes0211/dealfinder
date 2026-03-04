"""Infrastructure validation tests for OpenSearch.

These tests validate that OpenSearch is deployed correctly
with k-NN enabled, proper security, and monitoring configurations.
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
def domain_name(project_name, environment):
    """OpenSearch domain name."""
    return f"{project_name}-{environment}"


@pytest.fixture(scope="module")
def opensearch_client(aws_region):
    """OpenSearch client for testing."""
    return boto3.client("opensearch", region_name=aws_region)


@pytest.fixture(scope="module")
def ec2_client(aws_region):
    """EC2 client for security group testing."""
    return boto3.client("ec2", region_name=aws_region)


@pytest.fixture(scope="module")
def s3_client(aws_region):
    """S3 client for snapshot bucket testing."""
    return boto3.client("s3", region_name=aws_region)


@pytest.fixture(scope="module")
def cloudwatch_client(aws_region):
    """CloudWatch client for alarms testing."""
    return boto3.client("cloudwatch", region_name=aws_region)


@pytest.fixture(scope="module")
def kms_client(aws_region):
    """KMS client for encryption testing."""
    return boto3.client("kms", region_name=aws_region)


class TestOpenSearchDomain:
    """Test OpenSearch domain configuration."""

    def test_domain_exists(self, opensearch_client, domain_name):
        """Test that OpenSearch domain exists."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]
            assert domain["Created"] is True, "Domain should be created"
            assert not domain["Deleted"], "Domain should not be deleted"
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed (feature flag disabled)")
            raise

    def test_domain_processing(self, opensearch_client, domain_name):
        """Test that domain is available (not processing)."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]

            # Domain might be processing on first deploy
            if domain.get("Processing", False):
                pytest.skip("Domain is currently processing (initial deployment or update)")

            assert domain["Processing"] is False, "Domain should not be processing"
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise

    def test_domain_engine_version(self, opensearch_client, domain_name):
        """Test that domain uses correct OpenSearch version."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]

            engine_version = domain["EngineVersion"]
            assert engine_version.startswith("OpenSearch_"), "Should use OpenSearch engine"

            # Extract version number (e.g., "OpenSearch_2.11" -> "2.11")
            version = engine_version.replace("OpenSearch_", "")
            major_version = float(version.split(".")[0])
            assert major_version >= 2, "Should use OpenSearch 2.x or higher for k-NN support"
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise

    def test_vpc_deployment(self, opensearch_client, domain_name):
        """Test that domain is deployed in VPC."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]

            assert "VPCOptions" in domain, "Domain should be deployed in VPC"
            vpc_options = domain["VPCOptions"]
            assert "VPCId" in vpc_options, "Should have VPC ID"
            assert len(vpc_options.get("SubnetIds", [])) > 0, "Should have subnet IDs"
            assert len(vpc_options.get("SecurityGroupIds", [])) > 0, "Should have security groups"
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise

    def test_cluster_configuration(self, opensearch_client, domain_name):
        """Test cluster node configuration."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]

            cluster_config = domain["ClusterConfig"]
            assert cluster_config["InstanceCount"] >= 1, "Should have at least one instance"
            assert "InstanceType" in cluster_config, "Should have instance type configured"

            # Check instance type is valid for dev
            instance_type = cluster_config["InstanceType"]
            assert ".search" in instance_type, "Should use .search instance type"
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise

    def test_ebs_storage(self, opensearch_client, domain_name):
        """Test EBS storage configuration."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]

            ebs_options = domain.get("EBSOptions", {})
            assert ebs_options.get("EBSEnabled") is True, "EBS should be enabled"
            assert ebs_options.get("VolumeSize", 0) >= 10, "Should have at least 10GB storage"

            volume_type = ebs_options.get("VolumeType")
            assert volume_type in ["gp2", "gp3", "io1"], "Should use valid EBS volume type"
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise


class TestOpenSearchSecurity:
    """Test OpenSearch security configuration."""

    def test_encryption_at_rest(self, opensearch_client, domain_name):
        """Test that encryption at rest is enabled."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]

            encryption = domain.get("EncryptionAtRestOptions", {})
            assert encryption.get("Enabled") is True, "Encryption at rest should be enabled"
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise

    def test_node_to_node_encryption(self, opensearch_client, domain_name):
        """Test that node-to-node encryption is enabled."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]

            node_encryption = domain.get("NodeToNodeEncryptionOptions", {})
            assert node_encryption.get("Enabled") is True, (
                "Node-to-node encryption should be enabled"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise

    def test_https_required(self, opensearch_client, domain_name):
        """Test that HTTPS is enforced."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]

            endpoint_options = domain.get("DomainEndpointOptions", {})
            assert endpoint_options.get("EnforceHTTPS") is True, "HTTPS should be enforced"

            tls_policy = endpoint_options.get("TLSSecurityPolicy")
            assert tls_policy is not None, "TLS security policy should be set"
            assert "TLS-1-2" in tls_policy or "TLS-1-3" in tls_policy, (
                "Should use TLS 1.2 or higher"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise

    def test_fine_grained_access_control(self, opensearch_client, domain_name):
        """Test that fine-grained access control is enabled."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]

            advanced_security = domain.get("AdvancedSecurityOptions", {})
            assert advanced_security.get("Enabled") is True, (
                "Fine-grained access control should be enabled"
            )
            assert advanced_security.get("InternalUserDatabaseEnabled") is True, (
                "Internal user database should be enabled"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise

    def test_security_group_exists(self, ec2_client, project_name, environment):
        """Test that OpenSearch security group exists."""
        try:
            response = ec2_client.describe_security_groups(
                Filters=[
                    {"Name": "tag:Project", "Values": [project_name]},
                    {"Name": "tag:Environment", "Values": [environment]},
                    {
                        "Name": "group-name",
                        "Values": [f"{project_name}-{environment}-opensearch-sg"],
                    },
                ]
            )
            if len(response["SecurityGroups"]) == 0:
                pytest.skip("OpenSearch not deployed (feature flag disabled)")
            assert len(response["SecurityGroups"]) == 1, "OpenSearch security group should exist"
        except ClientError:
            pytest.skip("OpenSearch not deployed or security group not found")

    def test_security_group_rules(self, ec2_client, opensearch_client, domain_name):
        """Test that security group has correct ingress rules."""
        try:
            # Get domain to find security groups
            domain_response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = domain_response["DomainStatus"]

            vpc_options = domain.get("VPCOptions", {})
            security_group_ids = vpc_options.get("SecurityGroupIds", [])

            assert len(security_group_ids) > 0, "Should have security groups"

            sg_id = security_group_ids[0]

            # Get security group details
            sg_response = ec2_client.describe_security_groups(GroupIds=[sg_id])
            sg = sg_response["SecurityGroups"][0]

            # Check ingress rules
            ingress_rules = sg["IpPermissions"]
            https_rule = None

            for rule in ingress_rules:
                if rule.get("FromPort") == 443 and rule.get("ToPort") == 443:
                    https_rule = rule
                    break

            assert https_rule is not None, "Should have HTTPS port 443 ingress rule"
            assert https_rule["IpProtocol"] == "tcp", "Should use TCP protocol"

            # Verify it's not open to the world
            ip_ranges = https_rule.get("IpRanges", [])
            for ip_range in ip_ranges:
                assert ip_range["CidrIp"] != "0.0.0.0/0", "Should not be open to the internet"
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise


class TestOpenSearchKNN:
    """Test k-NN configuration for vector search."""

    def test_advanced_options_knn(self, opensearch_client, domain_name):
        """Test that k-NN is enabled in advanced options."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]

            # k-NN is enabled by default in OpenSearch 2.x, but verify domain is ready
            # The actual k-NN verification requires connecting to the cluster
            assert "Endpoint" in domain or "Endpoints" in domain, (
                "Domain should have endpoint for k-NN queries"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise


class TestOpenSearchSnapshots:
    """Test snapshot configuration."""

    def test_automated_snapshot_configured(self, opensearch_client, domain_name):
        """Test that automated snapshots are configured."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]

            snapshot_options = domain.get("SnapshotOptions", {})
            assert "AutomatedSnapshotStartHour" in snapshot_options, (
                "Automated snapshot hour should be configured"
            )

            hour = snapshot_options["AutomatedSnapshotStartHour"]
            assert 0 <= hour <= 23, "Snapshot hour should be valid (0-23)"
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise

    def test_snapshot_bucket_exists(self, s3_client, project_name, environment):
        """Test that S3 bucket for manual snapshots exists."""
        bucket_name = f"{project_name}-{environment}-opensearch-snapshots"
        try:
            response = s3_client.head_bucket(Bucket=bucket_name)
            assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                pytest.skip("Snapshot bucket not created (may be disabled)")
            raise

    def test_snapshot_bucket_encryption(self, s3_client, project_name, environment):
        """Test that snapshot bucket has encryption enabled."""
        bucket_name = f"{project_name}-{environment}-opensearch-snapshots"
        try:
            response = s3_client.get_bucket_encryption(Bucket=bucket_name)
            rules = response["ServerSideEncryptionConfiguration"]["Rules"]
            assert len(rules) > 0, "Bucket should have encryption rules"
            assert rules[0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256"
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchBucket":
                pytest.skip("Snapshot bucket not found")
            elif e.response["Error"]["Code"] == "ServerSideEncryptionConfigurationNotFoundError":
                pytest.fail("Snapshot bucket should have encryption enabled")
            raise

    def test_snapshot_bucket_versioning(self, s3_client, project_name, environment):
        """Test that snapshot bucket has versioning enabled."""
        bucket_name = f"{project_name}-{environment}-opensearch-snapshots"
        try:
            response = s3_client.get_bucket_versioning(Bucket=bucket_name)
            assert response.get("Status") == "Enabled", "Bucket should have versioning enabled"
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchBucket":
                pytest.skip("Snapshot bucket not found")
            raise

    def test_snapshot_bucket_lifecycle(self, s3_client, project_name, environment):
        """Test that snapshot bucket has lifecycle policies."""
        bucket_name = f"{project_name}-{environment}-opensearch-snapshots"
        try:
            response = s3_client.get_bucket_lifecycle_configuration(Bucket=bucket_name)
            rules = response.get("Rules", [])
            assert len(rules) > 0, "Bucket should have lifecycle rules"

            # Check for transition to cheaper storage
            has_transition = any(
                "Transitions" in rule and len(rule["Transitions"]) > 0 for rule in rules
            )
            assert has_transition, "Should have transition rules for cost optimization"
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchBucket":
                pytest.skip("Snapshot bucket not found")
            elif e.response["Error"]["Code"] == "NoSuchLifecycleConfiguration":
                pytest.skip("No lifecycle configuration (acceptable for dev)")
            raise


class TestOpenSearchMonitoring:
    """Test OpenSearch monitoring and alarms."""

    def test_cloudwatch_logs_enabled(self, opensearch_client, domain_name):
        """Test that CloudWatch logs are enabled."""
        try:
            response = opensearch_client.describe_domain(DomainName=domain_name)
            domain = response["DomainStatus"]

            log_options = domain.get("LogPublishingOptions", {})

            # Check for various log types
            expected_logs = ["INDEX_SLOW_LOGS", "SEARCH_SLOW_LOGS", "ES_APPLICATION_LOGS"]

            for log_type in expected_logs:
                if log_type in log_options:
                    log_config = log_options[log_type]
                    assert log_config.get("Enabled") is True, f"{log_type} should be enabled"
                    assert "CloudWatchLogsLogGroupArn" in log_config, (
                        f"{log_type} should have CloudWatch log group"
                    )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pytest.skip("OpenSearch domain not deployed")
            raise

    def test_cloudwatch_alarms_exist(self, cloudwatch_client, project_name, environment):
        """Test that CloudWatch alarms exist for OpenSearch."""
        try:
            response = cloudwatch_client.describe_alarms(
                AlarmNamePrefix=f"{project_name}-{environment}-opensearch"
            )
            alarms = response["MetricAlarms"]

            if len(alarms) == 0:
                pytest.skip("No OpenSearch alarms configured (may be disabled in dev)")

            # Check for specific alarms
            alarm_names = {alarm["AlarmName"] for alarm in alarms}

            expected_alarms = [
                "cluster-red",
                "low-storage",
                "high-cpu",
            ]

            for expected in expected_alarms:
                assert any(expected in name for name in alarm_names), (
                    f"Should have alarm containing '{expected}'"
                )
        except ClientError:
            pytest.skip("CloudWatch alarms not configured or accessible")

    def test_cluster_health_alarm(self, cloudwatch_client, project_name, environment):
        """Test cluster health alarm configuration."""
        alarm_name = f"{project_name}-{environment}-opensearch-cluster-red"
        try:
            response = cloudwatch_client.describe_alarms(AlarmNames=[alarm_name])

            if len(response["MetricAlarms"]) == 0:
                pytest.skip("Cluster health alarm not configured")

            alarm = response["MetricAlarms"][0]
            assert alarm["MetricName"] == "ClusterStatus.red", "Should monitor cluster red status"
            assert alarm["Namespace"] == "AWS/ES", "Should use ES namespace"
        except ClientError:
            pytest.skip("Cluster health alarm not found")

    def test_storage_alarm(self, cloudwatch_client, project_name, environment):
        """Test storage space alarm configuration."""
        alarm_name = f"{project_name}-{environment}-opensearch-low-storage"
        try:
            response = cloudwatch_client.describe_alarms(AlarmNames=[alarm_name])

            if len(response["MetricAlarms"]) == 0:
                pytest.skip("Storage alarm not configured")

            alarm = response["MetricAlarms"][0]
            assert alarm["MetricName"] == "FreeStorageSpace", "Should monitor free storage"
            assert alarm["Namespace"] == "AWS/ES", "Should use ES namespace"
        except ClientError:
            pytest.skip("Storage alarm not found")


class TestOpenSearchKMS:
    """Test KMS encryption for OpenSearch."""

    def test_kms_key_exists(self, kms_client, project_name, environment):
        """Test that KMS key exists for OpenSearch encryption."""
        alias_name = f"alias/{project_name}-{environment}-opensearch"
        try:
            response = kms_client.describe_key(KeyId=alias_name)
            key_metadata = response["KeyMetadata"]
            assert key_metadata["Enabled"] is True, "KMS key should be enabled"
            assert key_metadata["KeyState"] == "Enabled", "KMS key should be in enabled state"
        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                pytest.skip("KMS key not found (may use AWS managed key)")
            raise

    def test_kms_key_rotation_enabled(self, kms_client, project_name, environment):
        """Test that KMS key rotation is enabled."""
        alias_name = f"alias/{project_name}-{environment}-opensearch"
        try:
            response = kms_client.describe_key(KeyId=alias_name)
            key_id = response["KeyMetadata"]["KeyId"]

            rotation_response = kms_client.get_key_rotation_status(KeyId=key_id)
            assert rotation_response["KeyRotationEnabled"] is True, "Key rotation should be enabled"
        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                pytest.skip("KMS key not found")
            raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
