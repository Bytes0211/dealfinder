"""
Unit tests for CI/CD pipeline configurations.

Tests that CI and CD pipelines are correctly configured with proper
dependencies, AWS credentials, and Terraform commands.
"""

import re
import yaml
from pathlib import Path


class TestCIPipeline:
    """Test CI pipeline configuration."""

    @classmethod
    def setup_class(cls):
        """Load CI pipeline YAML."""
        cls.ci_file = Path(__file__).parent.parent.parent / ".github" / "workflows" / "ci.yml"
        with open(cls.ci_file) as f:
            cls.ci_config = yaml.safe_load(f)

    def test_ci_file_exists(self):
        """Test that CI pipeline file exists."""
        assert self.ci_file.exists(), "CI pipeline YAML should exist"

    def test_ci_name(self):
        """Test that CI pipeline has correct name."""
        assert self.ci_config["name"] == "CI Pipeline", \
            "CI pipeline should be named 'CI Pipeline'"

    def test_ci_triggers(self):
        """Test that CI pipeline has correct triggers."""
        # YAML parses 'on:' as boolean True
        triggers = self.ci_config.get("on") or self.ci_config.get(True)
        assert triggers is not None, "CI pipeline should have triggers"
        
        # Check push trigger
        assert "push" in triggers, "CI should trigger on push"
        assert "main" in triggers["push"]["branches"], \
            "CI should trigger on main branch"
        assert "develop" in triggers["push"]["branches"], \
            "CI should trigger on develop branch"
        
        # Check pull request trigger
        assert "pull_request" in triggers, \
            "CI should trigger on pull requests"

    def test_lint_and_test_job_exists(self):
        """Test that lint-and-test job exists."""
        assert "lint-and-test" in self.ci_config["jobs"], \
            "CI should have lint-and-test job"

    def test_python_version(self):
        """Test that correct Python version is used."""
        job = self.ci_config["jobs"]["lint-and-test"]
        
        # Find setup-python step
        setup_python = next(
            (step for step in job["steps"] if step.get("name") == "Set up Python"),
            None
        )
        
        assert setup_python is not None, "Should have Python setup step"
        assert setup_python["with"]["python-version"] == "3.12", \
            "Should use Python 3.12"

    def test_uv_installation(self):
        """Test that uv is installed."""
        job = self.ci_config["jobs"]["lint-and-test"]
        
        # Find uv install step
        install_uv = next(
            (step for step in job["steps"] if step.get("name") == "Install uv"),
            None
        )
        
        assert install_uv is not None, "Should have uv installation step"
        assert "curl -LsSf https://astral.sh/uv/install.sh" in install_uv["run"], \
            "Should install uv via official installer"

    def test_dependencies_installation(self):
        """Test that dependencies are installed correctly."""
        job = self.ci_config["jobs"]["lint-and-test"]
        
        # Find dependencies install step
        install_deps = next(
            (step for step in job["steps"] if step.get("name") == "Install dependencies"),
            None
        )
        
        assert install_deps is not None, "Should have dependencies installation step"
        
        run_script = install_deps["run"]
        
        # Check main package installation
        assert "uv pip install --system -e ." in run_script, \
            "Should install main package in editable mode"
        
        # Check dev dependencies
        assert "pytest" in run_script, "Should install pytest"
        assert "pytest-asyncio" in run_script, "Should install pytest-asyncio"
        assert "black" in run_script, "Should install black"
        assert "ruff" in run_script, "Should install ruff"
        assert "mypy" in run_script, "Should install mypy"

    def test_black_linting_step(self):
        """Test that black formatter check is run."""
        job = self.ci_config["jobs"]["lint-and-test"]
        
        # Find black step
        black_step = next(
            (step for step in job["steps"] if "black" in step.get("name", "").lower()),
            None
        )
        
        assert black_step is not None, "Should have black formatter step"
        assert "black --check" in black_step["run"], \
            "Should run black in check mode"
        assert "src/" in black_step["run"], "Should check src/ directory"
        assert "tests/" in black_step["run"], "Should check tests/ directory"

    def test_ruff_linting_step(self):
        """Test that ruff linter is run."""
        job = self.ci_config["jobs"]["lint-and-test"]
        
        # Find ruff step
        ruff_step = next(
            (step for step in job["steps"] if "ruff" in step.get("name", "").lower()),
            None
        )
        
        assert ruff_step is not None, "Should have ruff linter step"
        assert "ruff check" in ruff_step["run"], \
            "Should run ruff check"
        assert "src/" in ruff_step["run"], "Should check src/ directory"
        assert "tests/" in ruff_step["run"], "Should check tests/ directory"

    def test_mypy_type_checking_step(self):
        """Test that mypy type checker is run."""
        job = self.ci_config["jobs"]["lint-and-test"]
        
        # Find mypy step
        mypy_step = next(
            (step for step in job["steps"] if "mypy" in step.get("name", "").lower()),
            None
        )
        
        assert mypy_step is not None, "Should have mypy type checking step"
        assert "mypy src/" in mypy_step["run"], \
            "Should run mypy on src/ directory"

    def test_pytest_step(self):
        """Test that pytest is run."""
        job = self.ci_config["jobs"]["lint-and-test"]
        
        # Find pytest step
        pytest_step = next(
            (step for step in job["steps"] if step.get("name") == "Run tests"),
            None
        )
        
        assert pytest_step is not None, "Should have pytest step"
        assert "pytest tests/ -v" in pytest_step["run"], \
            "Should run pytest with verbose output"

    def test_security_scan_job_exists(self):
        """Test that security scan job exists."""
        assert "security-scan" in self.ci_config["jobs"], \
            "CI should have security-scan job"


class TestCDPipeline:
    """Test CD pipeline configuration."""

    @classmethod
    def setup_class(cls):
        """Load CD pipeline YAML."""
        cls.cd_file = Path(__file__).parent.parent.parent / ".github" / "workflows" / "cd.yml"
        with open(cls.cd_file) as f:
            cls.cd_config = yaml.safe_load(f)

    def test_cd_file_exists(self):
        """Test that CD pipeline file exists."""
        assert self.cd_file.exists(), "CD pipeline YAML should exist"

    def test_cd_name(self):
        """Test that CD pipeline has correct name."""
        assert self.cd_config["name"] == "CD Pipeline", \
            "CD pipeline should be named 'CD Pipeline'"

    def test_cd_triggers(self):
        """Test that CD pipeline has correct triggers."""
        # YAML parses 'on:' as boolean True
        triggers = self.cd_config.get("on") or self.cd_config.get(True)
        assert triggers is not None, "CD pipeline should have triggers"
        
        # Check push trigger
        assert "push" in triggers, "CD should trigger on push"
        assert "main" in triggers["push"]["branches"], \
            "CD should trigger on main branch only"
        
        # Check workflow_dispatch
        assert "workflow_dispatch" in triggers, \
            "CD should support manual triggers"

    def test_environment_variables(self):
        """Test that environment variables are set."""
        assert "env" in self.cd_config, "CD should have environment variables"
        assert self.cd_config["env"]["AWS_REGION"] == "us-east-1", \
            "AWS region should be us-east-1"
        assert self.cd_config["env"]["ECR_REPOSITORY"] == "dealfinder", \
            "ECR repository should be dealfinder"

    def test_deploy_infrastructure_job_exists(self):
        """Test that deploy-infrastructure job exists."""
        assert "deploy-infrastructure" in self.cd_config["jobs"], \
            "CD should have deploy-infrastructure job"

    def test_deploy_infrastructure_permissions(self):
        """Test that deploy-infrastructure job has correct permissions."""
        job = self.cd_config["jobs"]["deploy-infrastructure"]
        
        assert "permissions" in job, \
            "deploy-infrastructure should have permissions"
        assert job["permissions"]["id-token"] == "write", \
            "Should have id-token write permission for OIDC"
        assert job["permissions"]["contents"] == "read", \
            "Should have contents read permission"

    def test_aws_credentials_configuration(self):
        """Test that AWS credentials are configured correctly."""
        job = self.cd_config["jobs"]["deploy-infrastructure"]
        
        # Find AWS credentials step
        aws_creds_step = next(
            (step for step in job["steps"] 
             if step.get("name") == "Configure AWS credentials"),
            None
        )
        
        assert aws_creds_step is not None, \
            "Should have AWS credentials configuration step"
        
        assert aws_creds_step["uses"] == "aws-actions/configure-aws-credentials@v4", \
            "Should use AWS credentials action v4"
        
        # Check role-to-assume
        assert "role-to-assume" in aws_creds_step["with"], \
            "Should configure role-to-assume"
        assert "${{ secrets.AWS_ROLE_ARN }}" in aws_creds_step["with"]["role-to-assume"], \
            "Should use AWS_ROLE_ARN secret"
        
        # Check AWS region
        assert "aws-region" in aws_creds_step["with"], \
            "Should configure AWS region"
        assert "${{ env.AWS_REGION }}" in aws_creds_step["with"]["aws-region"], \
            "Should use AWS_REGION environment variable"

    def test_terraform_setup(self):
        """Test that Terraform is set up correctly."""
        job = self.cd_config["jobs"]["deploy-infrastructure"]
        
        # Find Terraform setup step
        terraform_setup = next(
            (step for step in job["steps"] 
             if step.get("name") == "Setup Terraform"),
            None
        )
        
        assert terraform_setup is not None, \
            "Should have Terraform setup step"
        
        assert terraform_setup["uses"] == "hashicorp/setup-terraform@v3", \
            "Should use HashiCorp Terraform action v3"
        
        assert "terraform_version" in terraform_setup["with"], \
            "Should specify Terraform version"
        assert "1.14" in terraform_setup["with"]["terraform_version"], \
            "Should use Terraform version ~> 1.14"

    def test_terraform_init_step(self):
        """Test that Terraform init is run."""
        job = self.cd_config["jobs"]["deploy-infrastructure"]
        
        # Find Terraform init step
        terraform_init = next(
            (step for step in job["steps"] 
             if step.get("name") == "Terraform Init"),
            None
        )
        
        assert terraform_init is not None, \
            "Should have Terraform init step"
        
        assert terraform_init["run"] == "terraform init", \
            "Should run terraform init"
        
        assert terraform_init["working-directory"] == "infrastructure/environments/dev", \
            "Should run in dev environment directory"

    def test_terraform_plan_step(self):
        """Test that Terraform plan is run."""
        job = self.cd_config["jobs"]["deploy-infrastructure"]
        
        # Find Terraform plan step
        terraform_plan = next(
            (step for step in job["steps"] 
             if step.get("name") == "Terraform Plan"),
            None
        )
        
        assert terraform_plan is not None, \
            "Should have Terraform plan step"
        
        assert "terraform plan" in terraform_plan["run"], \
            "Should run terraform plan"
        
        assert "-out=tfplan" in terraform_plan["run"], \
            "Should output plan to tfplan file"
        
        assert terraform_plan["working-directory"] == "infrastructure/environments/dev", \
            "Should run in dev environment directory"

    def test_terraform_apply_step(self):
        """Test that Terraform apply is run."""
        job = self.cd_config["jobs"]["deploy-infrastructure"]
        
        # Find Terraform apply step
        terraform_apply = next(
            (step for step in job["steps"] 
             if step.get("name") == "Terraform Apply"),
            None
        )
        
        assert terraform_apply is not None, \
            "Should have Terraform apply step"
        
        assert "terraform apply" in terraform_apply["run"], \
            "Should run terraform apply"
        
        assert "-auto-approve" in terraform_apply["run"], \
            "Should use auto-approve flag"
        
        assert "tfplan" in terraform_apply["run"], \
            "Should apply the tfplan file"
        
        assert terraform_apply["working-directory"] == "infrastructure/environments/dev", \
            "Should run in dev environment directory"

    def test_job_dependencies(self):
        """Test that jobs have correct dependencies."""
        # Check deploy-infrastructure depends on build-and-push
        deploy_infra = self.cd_config["jobs"]["deploy-infrastructure"]
        assert "needs" in deploy_infra, \
            "deploy-infrastructure should have dependencies"
        assert deploy_infra["needs"] == "build-and-push", \
            "deploy-infrastructure should depend on build-and-push"
        
        # Check deploy-lambda-functions depends on deploy-infrastructure
        deploy_lambda = self.cd_config["jobs"]["deploy-lambda-functions"]
        assert "needs" in deploy_lambda, \
            "deploy-lambda-functions should have dependencies"
        assert deploy_lambda["needs"] == "deploy-infrastructure", \
            "deploy-lambda-functions should depend on deploy-infrastructure"

    def test_post_deployment_tests_job(self):
        """Test that post-deployment tests job exists."""
        assert "post-deployment-tests" in self.cd_config["jobs"], \
            "CD should have post-deployment-tests job"
        
        job = self.cd_config["jobs"]["post-deployment-tests"]
        
        # Check it depends on deploy-lambda-functions
        assert job["needs"] == "deploy-lambda-functions", \
            "post-deployment-tests should depend on deploy-lambda-functions"
        
        # Check AWS credentials are configured
        aws_creds_step = next(
            (step for step in job["steps"] 
             if step.get("name") == "Configure AWS credentials"),
            None
        )
        assert aws_creds_step is not None, \
            "post-deployment-tests should configure AWS credentials"
