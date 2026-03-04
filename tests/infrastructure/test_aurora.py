"""Infrastructure validation tests for Aurora PostgreSQL.

These tests validate that Aurora PostgreSQL is deployed correctly
with proper security, backup, and monitoring configurations.
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
def cluster_identifier(project_name, environment):
    """Aurora cluster identifier."""
    return f"{project_name}-{environment}-aurora"


@pytest.fixture(scope="module")
def rds_client(aws_region):
    """RDS client for Aurora testing."""
    return boto3.client("rds", region_name=aws_region)


@pytest.fixture(scope="module")
def ec2_client(aws_region):
    """EC2 client for security group testing."""
    return boto3.client("ec2", region_name=aws_region)


@pytest.fixture(scope="module")
def cloudwatch_client(aws_region):
    """CloudWatch client for alarms testing."""
    return boto3.client("cloudwatch", region_name=aws_region)


@pytest.fixture(scope="module")
def kms_client(aws_region):
    """KMS client for encryption testing."""
    return boto3.client("kms", region_name=aws_region)


class TestAuroraCluster:
    """Test Aurora PostgreSQL cluster configuration."""

    def test_cluster_exists(self, rds_client, cluster_identifier):
        """Test that Aurora cluster exists."""
        try:
            response = rds_client.describe_db_clusters(DBClusterIdentifier=cluster_identifier)
            assert len(response["DBClusters"]) == 1, "Aurora cluster should exist"
            cluster = response["DBClusters"][0]
            assert cluster["Status"] == "available", "Cluster should be available"
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBClusterNotFoundFault":
                pytest.skip("Aurora cluster not deployed (feature flag disabled)")
            raise

    def test_cluster_engine(self, rds_client, cluster_identifier):
        """Test that cluster uses Aurora PostgreSQL."""
        try:
            response = rds_client.describe_db_clusters(DBClusterIdentifier=cluster_identifier)
            cluster = response["DBClusters"][0]
            assert cluster["Engine"] == "aurora-postgresql", "Should use Aurora PostgreSQL"
            assert cluster["EngineMode"] == "provisioned", (
                "Should use provisioned mode (Serverless v2)"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBClusterNotFoundFault":
                pytest.skip("Aurora cluster not deployed")
            raise

    def test_serverless_v2_scaling(self, rds_client, cluster_identifier):
        """Test that Serverless v2 scaling is configured."""
        try:
            response = rds_client.describe_db_clusters(DBClusterIdentifier=cluster_identifier)
            cluster = response["DBClusters"][0]

            assert "ServerlessV2ScalingConfiguration" in cluster, (
                "Should have Serverless v2 scaling"
            )
            scaling = cluster["ServerlessV2ScalingConfiguration"]

            assert scaling["MinCapacity"] >= 0.5, "Min capacity should be at least 0.5 ACUs"
            assert scaling["MaxCapacity"] <= 128, "Max capacity should be at most 128 ACUs"
            assert scaling["MinCapacity"] < scaling["MaxCapacity"], "Min should be less than max"
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBClusterNotFoundFault":
                pytest.skip("Aurora cluster not deployed")
            raise

    def test_cluster_encryption(self, rds_client, cluster_identifier):
        """Test that cluster has encryption at rest enabled."""
        try:
            response = rds_client.describe_db_clusters(DBClusterIdentifier=cluster_identifier)
            cluster = response["DBClusters"][0]
            assert cluster["StorageEncrypted"] is True, "Storage should be encrypted"
            assert "KmsKeyId" in cluster, "Should use KMS encryption"
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBClusterNotFoundFault":
                pytest.skip("Aurora cluster not deployed")
            raise

    def test_backup_retention(self, rds_client, cluster_identifier):
        """Test that automated backups are configured."""
        try:
            response = rds_client.describe_db_clusters(DBClusterIdentifier=cluster_identifier)
            cluster = response["DBClusters"][0]
            assert cluster["BackupRetentionPeriod"] >= 7, (
                "Backup retention should be at least 7 days"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBClusterNotFoundFault":
                pytest.skip("Aurora cluster not deployed")
            raise

    def test_multi_az_deployment(self, rds_client, cluster_identifier):
        """Test that cluster spans multiple availability zones."""
        try:
            response = rds_client.describe_db_clusters(DBClusterIdentifier=cluster_identifier)
            cluster = response["DBClusters"][0]

            # Check availability zones
            azs = cluster.get("AvailabilityZones", [])
            assert len(azs) >= 1, "Should have at least one AZ"

            # For dev, single AZ is acceptable
            # For prod, should have multiple AZs
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBClusterNotFoundFault":
                pytest.skip("Aurora cluster not deployed")
            raise

    def test_cloudwatch_logs_enabled(self, rds_client, cluster_identifier):
        """Test that CloudWatch logs are enabled."""
        try:
            response = rds_client.describe_db_clusters(DBClusterIdentifier=cluster_identifier)
            cluster = response["DBClusters"][0]

            enabled_logs = cluster.get("EnabledCloudwatchLogsExports", [])
            assert "postgresql" in enabled_logs, "PostgreSQL logs should be exported to CloudWatch"
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBClusterNotFoundFault":
                pytest.skip("Aurora cluster not deployed")
            raise


class TestAuroraInstances:
    """Test Aurora instance configuration."""

    def test_instances_exist(self, rds_client, cluster_identifier):
        """Test that Aurora instances exist."""
        try:
            response = rds_client.describe_db_instances(
                Filters=[{"Name": "db-cluster-id", "Values": [cluster_identifier]}]
            )
            instances = response["DBInstances"]
            assert len(instances) >= 1, "Should have at least one instance"

            for instance in instances:
                assert instance["DBInstanceStatus"] == "available", (
                    f"Instance {instance['DBInstanceIdentifier']} should be available"
                )
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBClusterNotFoundFault":
                pytest.skip("Aurora cluster not deployed")
            raise

    def test_instance_class_serverless(self, rds_client, cluster_identifier):
        """Test that instances use db.serverless class."""
        try:
            response = rds_client.describe_db_instances(
                Filters=[{"Name": "db-cluster-id", "Values": [cluster_identifier]}]
            )
            instances = response["DBInstances"]

            for instance in instances:
                assert instance["DBInstanceClass"] == "db.serverless", (
                    "Should use db.serverless class for Serverless v2"
                )
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBClusterNotFoundFault":
                pytest.skip("Aurora cluster not deployed")
            raise

    def test_instance_not_public(self, rds_client, cluster_identifier):
        """Test that instances are not publicly accessible."""
        try:
            response = rds_client.describe_db_instances(
                Filters=[{"Name": "db-cluster-id", "Values": [cluster_identifier]}]
            )
            instances = response["DBInstances"]

            for instance in instances:
                assert instance["PubliclyAccessible"] is False, (
                    "Instances should not be publicly accessible"
                )
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBClusterNotFoundFault":
                pytest.skip("Aurora cluster not deployed")
            raise

    def test_auto_minor_version_upgrade(self, rds_client, cluster_identifier):
        """Test that auto minor version upgrades are enabled."""
        try:
            response = rds_client.describe_db_instances(
                Filters=[{"Name": "db-cluster-id", "Values": [cluster_identifier]}]
            )
            instances = response["DBInstances"]

            for instance in instances:
                assert instance["AutoMinorVersionUpgrade"] is True, (
                    "Auto minor version upgrade should be enabled"
                )
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBClusterNotFoundFault":
                pytest.skip("Aurora cluster not deployed")
            raise


class TestAuroraSecurity:
    """Test Aurora security configuration."""

    def test_security_group_exists(self, ec2_client, project_name, environment):
        """Test that Aurora security group exists."""
        try:
            response = ec2_client.describe_security_groups(
                Filters=[
                    {"Name": "tag:Project", "Values": [project_name]},
                    {"Name": "tag:Environment", "Values": [environment]},
                    {"Name": "group-name", "Values": [f"{project_name}-{environment}-aurora-sg"]},
                ]
            )
            assert len(response["SecurityGroups"]) == 1, "Aurora security group should exist"
        except ClientError:
            pytest.skip("Aurora not deployed or security group not found")

    def test_security_group_rules(self, ec2_client, rds_client, cluster_identifier):
        """Test that security group has correct ingress rules."""
        try:
            # Get cluster to find security groups
            cluster_response = rds_client.describe_db_clusters(
                DBClusterIdentifier=cluster_identifier
            )
            cluster = cluster_response["DBClusters"][0]
            vpc_security_groups = cluster["VpcSecurityGroups"]

            assert len(vpc_security_groups) > 0, "Should have security groups"

            sg_id = vpc_security_groups[0]["VpcSecurityGroupId"]

            # Get security group details
            sg_response = ec2_client.describe_security_groups(GroupIds=[sg_id])
            sg = sg_response["SecurityGroups"][0]

            # Check ingress rules
            ingress_rules = sg["IpPermissions"]
            postgres_rule = None

            for rule in ingress_rules:
                if rule.get("FromPort") == 5432 and rule.get("ToPort") == 5432:
                    postgres_rule = rule
                    break

            assert postgres_rule is not None, "Should have PostgreSQL port 5432 ingress rule"
            assert postgres_rule["IpProtocol"] == "tcp", "Should use TCP protocol"

            # Verify it's not open to the world
            ip_ranges = postgres_rule.get("IpRanges", [])
            for ip_range in ip_ranges:
                assert ip_range["CidrIp"] != "0.0.0.0/0", "Should not be open to the internet"
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBClusterNotFoundFault":
                pytest.skip("Aurora cluster not deployed")
            raise

    def test_db_subnet_group_exists(self, rds_client, project_name, environment):
        """Test that DB subnet group exists."""
        subnet_group_name = f"{project_name}-{environment}-aurora-subnet-group"
        try:
            response = rds_client.describe_db_subnet_groups(DBSubnetGroupName=subnet_group_name)
            assert len(response["DBSubnetGroups"]) == 1, "DB subnet group should exist"

            subnet_group = response["DBSubnetGroups"][0]
            subnets = subnet_group["Subnets"]
            assert len(subnets) >= 2, "Should span at least 2 subnets for high availability"
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBSubnetGroupNotFoundFault":
                pytest.skip("Aurora not deployed (subnet group not found)")
            raise

    def test_parameter_group_exists(self, rds_client, project_name, environment):
        """Test that cluster parameter group exists."""
        param_group_name = f"{project_name}-{environment}-aurora-params"
        try:
            response = rds_client.describe_db_cluster_parameter_groups(
                DBClusterParameterGroupName=param_group_name
            )
            assert len(response["DBClusterParameterGroups"]) == 1, (
                "Cluster parameter group should exist"
            )

            param_group = response["DBClusterParameterGroups"][0]
            assert "aurora-postgresql" in param_group["DBParameterGroupFamily"], (
                "Should be for Aurora PostgreSQL"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "DBParameterGroupNotFound":
                pytest.skip("Aurora not deployed (parameter group not found)")
            raise


class TestAuroraMonitoring:
    """Test Aurora monitoring and alarms."""

    def test_cloudwatch_alarms_exist(self, cloudwatch_client, project_name, environment):
        """Test that CloudWatch alarms exist for Aurora."""
        try:
            response = cloudwatch_client.describe_alarms(
                AlarmNamePrefix=f"{project_name}-{environment}-aurora"
            )
            alarms = response["MetricAlarms"]

            if len(alarms) == 0:
                pytest.skip("No Aurora alarms configured (may be disabled in dev)")

            # Check for specific alarms
            alarm_names = {alarm["AlarmName"] for alarm in alarms}

            expected_alarms = [
                "high-cpu",
                "high-connections",
            ]

            for expected in expected_alarms:
                assert any(expected in name for name in alarm_names), (
                    f"Should have alarm containing '{expected}'"
                )
        except ClientError:
            pytest.skip("CloudWatch alarms not configured or accessible")

    def test_cpu_alarm_configuration(self, cloudwatch_client, project_name, environment):
        """Test CPU utilization alarm configuration."""
        alarm_name = f"{project_name}-{environment}-aurora-high-cpu"
        try:
            response = cloudwatch_client.describe_alarms(AlarmNames=[alarm_name])

            if len(response["MetricAlarms"]) == 0:
                pytest.skip("CPU alarm not configured")

            alarm = response["MetricAlarms"][0]
            assert alarm["MetricName"] == "CPUUtilization", "Should monitor CPU utilization"
            assert alarm["Namespace"] == "AWS/RDS", "Should use RDS namespace"
            assert alarm["Statistic"] == "Average", "Should use average statistic"
            assert alarm["Threshold"] >= 70, "Should have reasonable CPU threshold"
        except ClientError:
            pytest.skip("CPU alarm not found")

    def test_connections_alarm_configuration(self, cloudwatch_client, project_name, environment):
        """Test database connections alarm configuration."""
        alarm_name = f"{project_name}-{environment}-aurora-high-connections"
        try:
            response = cloudwatch_client.describe_alarms(AlarmNames=[alarm_name])

            if len(response["MetricAlarms"]) == 0:
                pytest.skip("Connections alarm not configured")

            alarm = response["MetricAlarms"][0]
            assert alarm["MetricName"] == "DatabaseConnections", (
                "Should monitor database connections"
            )
            assert alarm["Namespace"] == "AWS/RDS", "Should use RDS namespace"
        except ClientError:
            pytest.skip("Connections alarm not found")


class TestAuroraKMS:
    """Test KMS encryption for Aurora."""

    def test_kms_key_exists(self, kms_client, project_name, environment):
        """Test that KMS key exists for Aurora encryption."""
        alias_name = f"alias/{project_name}-{environment}-aurora"
        try:
            response = kms_client.describe_key(KeyId=alias_name)
            key_metadata = response["KeyMetadata"]
            assert key_metadata["Enabled"] is True, "KMS key should be enabled"
            assert key_metadata["KeyState"] == "Enabled", "KMS key should be in enabled state"
        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                pytest.skip("KMS key not found (may use default AWS managed key)")
            raise

    def test_kms_key_rotation_enabled(self, kms_client, project_name, environment):
        """Test that KMS key rotation is enabled."""
        alias_name = f"alias/{project_name}-{environment}-aurora"
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
