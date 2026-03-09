# Deal Finder — Lambda Deployment & Maintenance Guide

## Overview

Deal Finder runs six Lambda functions that form the backend:

| Function | Handler | Purpose |
|----------|---------|---------|
| `dealfinder-{env}-api` | `dealfinder.api.main.handler` | FastAPI REST API (via Mangum) |
| `dealfinder-{env}-scanner` | `dealfinder.agents.scanner.handler` | RSS feed scraping |
| `dealfinder-{env}-evaluator` | `dealfinder.agents.evaluator.handler` | Bedrock price estimation |
| `dealfinder-{env}-messenger` | `dealfinder.agents.messenger.handler` | SNS/SES notifications |
| `dealfinder-{env}-pipeline-summary` | `dealfinder.agents.pipeline_summary.handler` | Per-feed no-deals dedup |
| `dealfinder-{env}-watchlist` | `dealfinder.agents.watchlist.handler` | Tavily + Bedrock deal discovery (30-min schedule) |

All Lambdas use **Python 3.12**, run inside the VPC (private subnets), and share a common security group allowing outbound HTTPS, HTTP, and PostgreSQL (port 5432) to Aurora.

Terraform provisions the functions with a placeholder zip. Real code is deployed via CI/CD or the scripts below.

---

## Deployment Scripts

All scripts live in the `scripts/` directory and follow the same pattern: build a zip package with `uv pip install`, copy source, then push to AWS Lambda.

### `deploy-lambda.sh` — Deploy One or More Lambdas

The primary deployment script. Builds the package **once** and deploys it to one or more Lambda functions.

**Usage:**

```bash
# Deploy all six functions to dev
./scripts/deploy-lambda.sh dev

# Deploy only the API Lambda to prod
./scripts/deploy-lambda.sh prod api

# Deploy multiple specific functions
./scripts/deploy-lambda.sh prod api scanner evaluator
```

**Supported function names:** `api`, `scanner`, `evaluator`, `messenger`, `pipeline-summary`, `watchlist`

**What it does:**

1. Creates a temp build directory
2. Installs all Python dependencies via `uv pip install --target` (Python 3.12)
3. Copies `src/dealfinder/` into the package
4. Zips the package (excluding `.pyc` and `__pycache__`)
5. For each target function, calls `aws lambda update-function-code` with the zip
6. Waits for each update to complete (`aws lambda wait function-updated`)
7. Cleans up the temp directory

**When to use:** After any change to Python source code or dependencies. This is the script called by CI/CD.

### `deploy-api-lambda.sh` — Deploy API Lambda Only (Legacy)

An older, single-function variant that deploys only the API Lambda.

**Usage:**

```bash
./scripts/deploy-api-lambda.sh prod
```

**Note:** `deploy-lambda.sh prod api` does the same thing. This script exists for backward compatibility and can be used as a quick shortcut for API-only deploys.

### `run-migrations-lambda.sh` — Run Alembic Migrations via Lambda

Runs database migrations by temporarily swapping the API Lambda's handler to the migration handler, invoking it, then restoring the original handler.

**Usage:**

```bash
./scripts/run-migrations-lambda.sh prod
```

**What it does:**

1. Saves the original handler (`dealfinder.api.main.handler`)
2. Swaps the handler to `dealfinder.db.migration_handler.handler`
3. Waits for the configuration update to propagate
4. Invokes the Lambda synchronously with `{"action": "migrate"}`
5. Checks the response for `"status": "success"`
6. **Always** restores the original handler on exit (via a `trap` on `EXIT`)

**Why this approach:** The API Lambda already has VPC access to Aurora. Instead of provisioning a separate migration Lambda, this script reuses the API Lambda's network configuration and IAM role to run `alembic upgrade head` inside the VPC.

**Safety:** The `trap cleanup EXIT` ensures the handler is restored even if the script fails mid-execution. If migration reports a non-success status, the script exits with code 1 and prints the CloudWatch log group to check.

**When to use:** After any Alembic migration is added (new files in `src/dealfinder/db/alembic/versions/`). Always deploy the latest code first, then run migrations.

---

## CI/CD — GitHub Actions

### Backend Workflow (`.github/workflows/backend.yml`)

**Triggers:**

- **Automatic:** Push to `main` touching `src/`, `infrastructure/`, `scripts/`, `tests/`, `pyproject.toml`, or `uv.lock`
- **Manual:** `workflow_dispatch` with environment, function selection, and migration toggle

**Pipeline steps:**

1. Checkout → Setup Python 3.12 + uv
2. `uv sync --all-extras --dev` → install dependencies
3. `uv run pytest tests/unit/ -v` → run unit tests (deploy aborts on failure)
4. Configure AWS credentials via OIDC (`AWS_DEPLOY_ROLE_ARN`)
5. Deploy Lambdas:
   - On push: `./scripts/deploy-lambda.sh prod` (all functions)
   - On dispatch with functions specified: `./scripts/deploy-lambda.sh {env} {functions}`
6. Optionally run migrations: `./scripts/run-migrations-lambda.sh {env}`

**Manual dispatch inputs:**

- `environment` — `dev` or `prod` (default: `prod`)
- `functions` — space-separated list (default: all)
- `run_migrations` — boolean (default: `false`)

### Frontend Workflow (`.github/workflows/frontend.yml`)

Deploys the React SPA. Not Lambda-related, but included for completeness:

- Triggers on push to `main` touching `frontend/`
- Builds with Vite, syncs to S3, invalidates CloudFront

---

## Common Deployment Workflows

### Standard Code Change

```bash
# 1. Make changes, run tests locally
uv run pytest tests/unit/ -v

# 2. Push to main — CI/CD handles deploy automatically
git push origin main
```

### Manual Deploy (Specific Functions)

```bash
# Deploy just the evaluator and watchlist to prod
./scripts/deploy-lambda.sh prod evaluator watchlist
```

### Schema Change (Migration Required)

```bash
# 1. Create the Alembic migration
uv run alembic revision --autogenerate -m "add_new_column"

# 2. Deploy code first (includes new migration file)
./scripts/deploy-lambda.sh prod

# 3. Run the migration
./scripts/run-migrations-lambda.sh prod
```

Or via GitHub Actions: trigger `workflow_dispatch` with `run_migrations: true`.

### Dependency Update

```bash
# 1. Update pyproject.toml or uv.lock
uv add new-package

# 2. Redeploy all Lambdas (the zip includes all dependencies)
./scripts/deploy-lambda.sh prod
```

---

## Maintenance & Troubleshooting

### Viewing Logs

Each Lambda writes to its own CloudWatch log group:

```bash
# Tail recent logs for a specific function
aws logs tail /aws/lambda/dealfinder-prod-api --follow

# Search for errors
aws logs filter-log-events \
    --log-group-name /aws/lambda/dealfinder-prod-evaluator \
    --filter-pattern "ERROR"
```

### Checking Lambda Status

```bash
# Get current configuration for a function
aws lambda get-function-configuration \
    --function-name dealfinder-prod-api \
    --query '{Handler: Handler, MemorySize: MemorySize, Timeout: Timeout, LastModified: LastModified}' \
    --no-cli-pager
```

### Invoking a Lambda Manually

```bash
# Test the scanner with a dry run
aws lambda invoke \
    --function-name dealfinder-prod-scanner \
    --payload '{}' \
    --cli-binary-format raw-in-base64-out \
    --no-cli-pager \
    /tmp/scanner-response.json

cat /tmp/scanner-response.json
```

### Updating Environment Variables

Environment variables are managed in Terraform (`infrastructure/modules/pipeline/main.tf`). To update:

1. Edit the `environment.variables` block for the relevant Lambda resource
2. Run `terraform apply` from `infrastructure/environments/dev/`

Do **not** update env vars via the AWS CLI or console — Terraform will revert them on the next apply.

### Recovering from a Failed Migration

If `run-migrations-lambda.sh` fails:

1. The handler is **automatically restored** (trap ensures this)
2. Check CloudWatch logs: `/aws/lambda/dealfinder-{env}-api`
3. Fix the migration, redeploy, and rerun:
   ```bash
   ./scripts/deploy-lambda.sh prod api
   ./scripts/run-migrations-lambda.sh prod
   ```

### Package Size Concerns

The deployment zip includes all Python dependencies. If it approaches the 250 MB unzipped Lambda limit:

- Check the current size (printed during deploy as `Size: ...`)
- Consider using Lambda layers for large, stable dependencies
- Exclude test files and dev dependencies (already handled — `uv pip install` only installs runtime deps)

---

## Prerequisites

- **AWS CLI v2** configured with appropriate credentials
- **uv** package manager installed
- **Python 3.12** available
- IAM permissions for `lambda:UpdateFunctionCode`, `lambda:UpdateFunctionConfiguration`, `lambda:InvokeFunction`, `lambda:GetFunction`, and `logs:*`
- For CI/CD: `AWS_DEPLOY_ROLE_ARN` secret configured in GitHub repository settings
