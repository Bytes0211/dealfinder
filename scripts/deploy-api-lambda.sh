#!/bin/bash
# Build and deploy the Deal Finder API Lambda function.
# Usage: ./scripts/deploy-api-lambda.sh [environment]
# Example: ./scripts/deploy-api-lambda.sh prod

set -e

ENVIRONMENT="${1:-prod}"
FUNCTION_NAME="dealfinder-${ENVIRONMENT}-api"
BUILD_DIR="$(mktemp -d)"
ZIP_PATH="${BUILD_DIR}/lambda.zip"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "================================================"
echo "Deploy API Lambda"
echo "Function : ${FUNCTION_NAME}"
echo "Build dir: ${BUILD_DIR}"
echo "================================================"

# Install dependencies into build dir
echo ""
echo "▶ Installing dependencies..."
# Install all dependencies from pyproject.toml (email-validator, etc. included)
uv pip install \
    --target "${BUILD_DIR}/package" \
    --python 3.12 \
    --no-cache \
    "${PROJECT_ROOT}" 2>/dev/null || \
uv pip install \
    --target "${BUILD_DIR}/package" \
    --python 3.12 \
    --no-cache \
    fastapi mangum "sqlalchemy[asyncio]" asyncpg aiosqlite \
    "pydantic[email]>=2" "pydantic-settings>=2" boto3 httpx \
    feedparser openai "email-validator"

# Copy application source
echo "▶ Copying source..."
cp -r "${PROJECT_ROOT}/src/dealfinder" "${BUILD_DIR}/package/"

# Zip everything
echo "▶ Creating zip..."
cd "${BUILD_DIR}/package"
zip -r "${ZIP_PATH}" . -x "*.pyc" -x "*/__pycache__/*" -x "*.dist-info/*" > /dev/null
echo "   Size: $(du -sh "${ZIP_PATH}" | cut -f1)"

# Deploy to Lambda
echo ""
echo "▶ Updating Lambda function code..."
aws lambda update-function-code \
    --function-name "${FUNCTION_NAME}" \
    --zip-file "fileb://${ZIP_PATH}" \
    --no-cli-pager \
    --query '{FunctionName: FunctionName, CodeSize: CodeSize, LastModified: LastModified}'

echo ""
echo "▶ Waiting for update to complete..."
aws lambda wait function-updated \
    --function-name "${FUNCTION_NAME}" \
    --no-cli-pager

echo ""
echo "================================================"
echo "✓ Deploy complete: ${FUNCTION_NAME}"
echo "================================================"

# Cleanup
rm -rf "${BUILD_DIR}"
