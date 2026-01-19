"""
Unit tests for README.md documentation validation.

Tests verify that README.md exists, contains proper structure, and includes
all required sections for project documentation.
"""

import os
import re
from pathlib import Path

import pytest


class TestReadmeExists:
    """Test cases for README.md file presence."""

    def test_readme_file_exists(self):
        """Verify README.md file is added to the repository."""
        readme_path = Path(__file__).parent.parent / "README.md"
        assert readme_path.exists(), "README.md file should exist in repository root"

    def test_readme_is_file_not_directory(self):
        """Verify README.md is a file, not a directory."""
        readme_path = Path(__file__).parent.parent / "README.md"
        assert readme_path.is_file(), "README.md should be a file"

    def test_readme_is_not_empty(self):
        """Verify README.md contains content."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()
        assert len(content.strip()) > 0, "README.md should not be empty"


class TestReadmeStructure:
    """Test cases for README.md structure and required sections."""

    @pytest.fixture
    def readme_content(self):
        """Load README.md content for testing."""
        readme_path = Path(__file__).parent.parent / "README.md"
        return readme_path.read_text()

    def test_readme_has_project_title(self, readme_content):
        """Verify README.md starts with a project title."""
        lines = readme_content.split('\n')
        # First non-empty line should be an h1 heading
        first_line = next((line for line in lines if line.strip()), None)
        assert first_line is not None, "README should have content"
        assert first_line.startswith('# '), "README should start with an h1 heading"

    def test_readme_has_architecture_section(self, readme_content):
        """Verify README.md contains architecture description section."""
        # Check for architecture-related headers
        architecture_patterns = [
            r'#+\s*.*[Aa]rchitecture',
            r'#+\s*.*[Ss]ystem\s+[Dd]esign',
            r'#+\s*.*[Cc]omponents?',
        ]
        
        found_architecture = any(
            re.search(pattern, readme_content, re.MULTILINE) 
            for pattern in architecture_patterns
        )
        
        assert found_architecture, (
            "README.md should contain an architecture section "
            "(e.g., 'Architecture Overview', 'System Design', 'Components')"
        )

    def test_readme_has_technology_stack_section(self, readme_content):
        """Verify README.md contains technology stack description."""
        # Check for technology/tech stack headers
        tech_patterns = [
            r'#+\s*.*[Tt]echnology\s+[Ss]tack',
            r'#+\s*.*[Tt]ech\s+[Ss]tack',
            r'#+\s*.*[Tt]echnologies',
        ]
        
        found_tech_stack = any(
            re.search(pattern, readme_content, re.MULTILINE)
            for pattern in tech_patterns
        )
        
        assert found_tech_stack, (
            "README.md should contain a technology stack section "
            "(e.g., 'Technology Stack', 'Tech Stack', 'Technologies')"
        )

    def test_readme_has_roadmap_section(self, readme_content):
        """Verify README.md contains roadmap information."""
        # Check for roadmap-related headers
        roadmap_patterns = [
            r'#+\s*.*[Rr]oadmap',
            r'#+\s*.*[Mm]ilestones?',
            r'#+\s*.*[Pp]hases?',
        ]
        
        found_roadmap = any(
            re.search(pattern, readme_content, re.MULTILINE)
            for pattern in roadmap_patterns
        )
        
        assert found_roadmap, (
            "README.md should contain a roadmap section "
            "(e.g., 'Roadmap', 'Milestones', 'Phases')"
        )

    def test_readme_has_contact_section(self, readme_content):
        """Verify README.md contains contact information section."""
        # Check for contact-related headers
        contact_patterns = [
            r'#+\s*.*[Cc]ontact',
            r'#+\s*.*[Ss]upport',
            r'#+\s*.*[Cc]ontributors?',
            r'#+\s*.*[Aa]uthors?',
        ]
        
        found_contact = any(
            re.search(pattern, readme_content, re.MULTILINE)
            for pattern in contact_patterns
        )
        
        assert found_contact, (
            "README.md should contain a contact section "
            "(e.g., 'Contact', 'Support', 'Contributors', 'Authors')"
        )


class TestReadmePerformanceTargets:
    """Test cases for performance targets documentation."""

    @pytest.fixture
    def readme_content(self):
        """Load README.md content for testing."""
        readme_path = Path(__file__).parent.parent / "README.md"
        return readme_path.read_text()

    def test_readme_has_performance_section(self, readme_content):
        """Verify README.md includes performance targets section."""
        performance_patterns = [
            r'#+\s*.*[Pp]erformance',
            r'#+\s*.*[Mm]etrics?',
            r'#+\s*.*[Tt]argets?',
            r'#+\s*.*[Ss][Ll][Aa]',
        ]
        
        found_performance = any(
            re.search(pattern, readme_content, re.MULTILINE)
            for pattern in performance_patterns
        )
        
        assert found_performance, (
            "README.md should contain a performance targets section "
            "(e.g., 'Performance Targets', 'Metrics', 'SLA')"
        )

    def test_performance_section_has_table(self, readme_content):
        """Verify performance targets are presented in a table format."""
        # Look for markdown table syntax (headers with pipes)
        table_pattern = r'\|.*\|.*\|'
        has_table = re.search(table_pattern, readme_content)
        
        assert has_table, (
            "README.md should include a table for performance targets"
        )

    def test_performance_includes_key_metrics(self, readme_content):
        """Verify performance section includes key metrics."""
        # Convert to lowercase for case-insensitive matching
        content_lower = readme_content.lower()
        
        # Check for common performance-related terms
        performance_terms = [
            'latency',
            'throughput',
            'availability',
            'uptime',
            'response time',
        ]
        
        found_terms = [term for term in performance_terms if term in content_lower]
        
        assert len(found_terms) >= 2, (
            f"Performance section should include key metrics. "
            f"Found: {found_terms}. Expected at least 2 of: {performance_terms}"
        )


class TestReadmeCostEstimation:
    """Test cases for cost estimation documentation."""

    @pytest.fixture
    def readme_content(self):
        """Load README.md content for testing."""
        readme_path = Path(__file__).parent.parent / "README.md"
        return readme_path.read_text()

    def test_readme_has_cost_section(self, readme_content):
        """Verify README.md includes cost estimation section."""
        cost_patterns = [
            r'#+\s*.*[Cc]ost',
            r'#+\s*.*[Pp]ricing',
            r'#+\s*.*[Bb]udget',
        ]
        
        found_cost = any(
            re.search(pattern, readme_content, re.MULTILINE)
            for pattern in cost_patterns
        )
        
        assert found_cost, (
            "README.md should contain a cost estimation section "
            "(e.g., 'Cost Estimation', 'Pricing', 'Budget')"
        )

    def test_cost_section_has_monetary_values(self, readme_content):
        """Verify cost section includes monetary values."""
        # Look for currency symbols or cost indicators
        cost_indicators = [
            r'\$\d+',  # Dollar amounts like $100
            r'\d+\s*USD',  # USD amounts
            r'\d+\s*dollars?',  # Dollar text
        ]
        
        found_costs = any(
            re.search(pattern, readme_content, re.IGNORECASE)
            for pattern in cost_indicators
        )
        
        assert found_costs, (
            "Cost estimation section should include monetary values "
            "(e.g., $100, USD, dollars)"
        )

    def test_cost_section_has_table_or_list(self, readme_content):
        """Verify cost information is organized in a table or list."""
        # Check for either markdown table or list structure
        has_table = bool(re.search(r'\|.*\|.*\|', readme_content))
        has_list = bool(re.search(r'^[\s]*[-*]\s+.*\$', readme_content, re.MULTILINE))
        
        assert has_table or has_list, (
            "Cost estimation should be presented in a table or list format"
        )

    def test_cost_breakdown_includes_components(self, readme_content):
        """Verify cost breakdown includes infrastructure components."""
        content_lower = readme_content.lower()
        
        # Look for common infrastructure cost components
        # Based on the architecture, expect AWS services
        infrastructure_terms = [
            'aws',
            'database',
            'storage',
            'compute',
            'kafka',
            'msk',
            'opensearch',
            'lambda',
            'fargate',
            'rds',
            'dynamodb',
            's3',
        ]
        
        found_terms = [term for term in infrastructure_terms if term in content_lower]
        
        assert len(found_terms) >= 3, (
            f"Cost breakdown should mention infrastructure components. "
            f"Found: {found_terms}. Expected at least 3 infrastructure terms."
        )


class TestReadmeDetailedContent:
    """Test cases for detailed project documentation."""

    @pytest.fixture
    def readme_content(self):
        """Load README.md content for testing."""
        readme_path = Path(__file__).parent.parent / "README.md"
        return readme_path.read_text()

    def test_readme_has_project_description(self, readme_content):
        """Verify README.md contains a project description."""
        # Should have substantial content in the first 500 characters
        first_section = readme_content[:500]
        # Remove markdown syntax and whitespace
        cleaned = re.sub(r'[#*`\-\[\]()]', '', first_section)
        word_count = len(cleaned.split())
        
        assert word_count >= 10, (
            "README should start with a meaningful project description "
            f"(found {word_count} words, expected at least 10)"
        )

    def test_architecture_section_has_components(self, readme_content):
        """Verify architecture section describes system components."""
        content_lower = readme_content.lower()
        
        # Look for component-related terms
        component_terms = [
            'agent',
            'service',
            'component',
            'module',
            'layer',
            'microservice',
        ]
        
        found_terms = [term for term in component_terms if term in content_lower]
        
        assert len(found_terms) >= 1, (
            "Architecture section should describe system components"
        )

    def test_technology_stack_lists_technologies(self, readme_content):
        """Verify technology stack section lists specific technologies."""
        content_lower = readme_content.lower()
        
        # Based on WARP.md, expect these technologies
        expected_technologies = [
            'python',
            'kafka',
            'aws',
            'spark',
        ]
        
        found_technologies = [
            tech for tech in expected_technologies 
            if tech in content_lower
        ]
        
        assert len(found_technologies) >= 3, (
            f"Technology stack should list specific technologies. "
            f"Found: {found_technologies}. "
            f"Expected at least 3 of: {expected_technologies}"
        )

    def test_roadmap_has_phases_or_milestones(self, readme_content):
        """Verify roadmap includes phases, milestones, or checkboxes."""
        # Look for roadmap structure indicators
        has_checkboxes = bool(re.search(r'[-*]\s*\[[ x]\]', readme_content))
        has_phases = bool(re.search(r'[Pp]hase\s+\d+', readme_content))
        has_milestones = bool(re.search(r'[Mm]ilestone\s+\d+', readme_content))
        has_numbered_list = bool(re.search(r'^\d+\.', readme_content, re.MULTILINE))
        
        assert any([has_checkboxes, has_phases, has_milestones, has_numbered_list]), (
            "Roadmap should include phases, milestones, or task lists"
        )
