#!/bin/bash
# Build the Deal Finder Python package once and deploy to one or more Lambda functions.
#
# Usage: ./scripts/deploy-lambda.sh <environment> [function...] 
# Examples:
#   ./scripts/deploy-lambda.sh dev                              # all functions
#   ./scripts/deploy-lambda.sh dev api                         # API Lambda only
#   ./scripts/deploy-lambda.sh dev api scanner evaluator       # multiple
#   ./scripts/deploy-lambda.sh prod api scanner evaluator messenger
#
# Supported function names: api, scanner, evaluator, messenger, pipeline-summary

set -e

ENVIRONMENT="${1:-dev}"
shift || true

# Default: deploy all four if none specified
FUNCTIONS=("${@}")
if [ ${#FUNCTIONS[@]} -eq 0 ]; then
  FUNCTIONS=(api scanner evaluator messenger pipeline-summary)
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$(mktemp -d)"
ZIP_PATH="${BUILD_DIR}/lambda.zip"

echo "================================================"
echo "Deploy Deal Finder Lambdas"
echo "Environment : ${ENVIRONMENT}"
echo "Functions   : ${FUNCTIONS[*]}"
echo "Build dir   : ${BUILD_DIR}"
echo "================================================"

# ── Build ────────────────────────────────────────────────────────────────────

echo ""
echo "▶ Installing dependencies..."
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
    feedparser openai "email-validator" tavily-python

echo "▶ Copying source..."
cp -r "${PROJECT_ROOT}/src/dealfinder" "${BUILD_DIR}/package/"

echo "▶ Creating zip..."
cd "${BUILD_DIR}/package"
zip -r "${ZIP_PATH}" . -x "*.pyc" -x "*/__pycache__/*" > /dev/null
echo "   Size: $(du -sh "${ZIP_PATH}" | cut -f1)"

# ── Deploy ───────────────────────────────────────────────────────────────────

for FUNC in "${FUNCTIONS[@]}"; do
  FUNCTION_NAME="dealfinder-${ENVIRONMENT}-${FUNC}"
  echo ""
  echo "▶ Deploying ${FUNCTION_NAME}..."
  aws lambda update-function-code \
      --function-name "${FUNCTION_NAME}" \
      --zip-file "fileb://${ZIP_PATH}" \
      --no-cli-pager \
      --query '{FunctionName: FunctionName, CodeSize: CodeSize, LastModified: LastModified}'

  echo "   Waiting for update to complete..."
  aws lambda wait function-updated \
      --function-name "${FUNCTION_NAME}" \
      --no-cli-pager
  echo "   ✓ ${FUNCTION_NAME} deployed"
done

# ── Cleanup ──────────────────────────────────────────────────────────────────
rm -rf "${BUILD_DIR}"

echo ""
echo "================================================"
echo "✓ All functions deployed to ${ENVIRONMENT}"
echo "================================================"
