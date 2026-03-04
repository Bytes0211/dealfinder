# Test Suite

Unit tests for the Deal Finder project documentation and code.

## Current Tests

### test_readme.py

Validates the structure and content of the project README.md file.

**Test Coverage:**

1. **File Existence Tests** (`TestReadmeExists`)
   - Verifies README.md file exists in repository root
   - Ensures it's a file, not a directory
   - Confirms the file is not empty

2. **Structure Tests** (`TestReadmeStructure`)
   - Validates project title (h1 heading)
   - Checks for architecture description section
   - Verifies technology stack section exists
   - Confirms roadmap section is present
   - Ensures contact information section exists

3. **Performance Targets Tests** (`TestReadmePerformanceTargets`)
   - Validates performance targets section exists
   - Checks for table format presentation
   - Verifies inclusion of key metrics (latency, throughput, availability, etc.)

4. **Cost Estimation Tests** (`TestReadmeCostEstimation`)
   - Confirms cost estimation section exists
   - Validates monetary values are included
   - Checks for organized table or list format
   - Verifies infrastructure component breakdown (AWS services, etc.)

5. **Detailed Content Tests** (`TestReadmeDetailedContent`)
   - Validates meaningful project description
   - Ensures architecture section describes components
   - Checks technology stack lists specific technologies
   - Verifies roadmap has structured phases/milestones

## Running Tests

### Prerequisites

Install Python 3.12+ and create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r tests/requirements.txt
```

### Run All Tests

```bash
pytest tests/test_readme.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_readme.py::TestReadmeStructure -v
```

### Run Single Test

```bash
pytest tests/test_readme.py::TestReadmeExists::test_readme_file_exists -v
```

## Expected Results

All tests should pass with the current README.md structure:

```
tests/test_readme.py::TestReadmeExists::test_readme_file_exists PASSED
tests/test_readme.py::TestReadmeExists::test_readme_is_file_not_directory PASSED
tests/test_readme.py::TestReadmeExists::test_readme_is_not_empty PASSED
tests/test_readme.py::TestReadmeStructure::test_readme_has_project_title PASSED
tests/test_readme.py::TestReadmeStructure::test_readme_has_architecture_section PASSED
tests/test_readme.py::TestReadmeStructure::test_readme_has_technology_stack_section PASSED
tests/test_readme.py::TestReadmeStructure::test_readme_has_roadmap_section PASSED
tests/test_readme.py::TestReadmeStructure::test_readme_has_contact_section PASSED
tests/test_readme.py::TestReadmePerformanceTargets::test_readme_has_performance_section PASSED
tests/test_readme.py::TestReadmePerformanceTargets::test_performance_section_has_table PASSED
tests/test_readme.py::TestReadmePerformanceTargets::test_performance_includes_key_metrics PASSED
tests/test_readme.py::TestReadmeCostEstimation::test_readme_has_cost_section PASSED
tests/test_readme.py::TestReadmeCostEstimation::test_cost_section_has_monetary_values PASSED
tests/test_readme.py::TestReadmeCostEstimation::test_cost_section_has_table_or_list PASSED
tests/test_readme.py::TestReadmeCostEstimation::test_cost_breakdown_includes_components PASSED
tests/test_readme.py::TestReadmeDetailedContent::test_readme_has_project_description PASSED
tests/test_readme.py::TestReadmeDetailedContent::test_architecture_section_has_components PASSED
tests/test_readme.py::TestReadmeDetailedContent::test_technology_stack_lists_technologies PASSED
tests/test_readme.py::TestReadmeDetailedContent::test_roadmap_has_phases_or_milestones PASSED

===================== 19 passed in 0.02s =====================
```

## Future Tests

As the project develops, additional test files will be added:
- `test_agents.py` - Agent implementation tests
- `test_api.py` - FastAPI endpoint tests
- `test_ml_models.py` - ML model tests
- `test_kafka_integration.py` - Streaming integration tests
