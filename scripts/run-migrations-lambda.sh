#!/bin/bash
# Run Alembic migrations via the API Lambda (which has VPC access to Aurora).
# The script temporarily swaps the Lambda handler, invokes it synchronously,
# then restores the original API handler.
#
# Usage: ./scripts/run-migrations-lambda.sh [environment]
# Example: ./scripts/run-migrations-lambda.sh prod

set -e

ENVIRONMENT="${1:-prod}"
FUNCTION_NAME="dealfinder-${ENVIRONMENT}-api"
ORIGINAL_HANDLER="dealfinder.api.main.handler"
MIGRATION_HANDLER="dealfinder.db.migration_handler.handler"
RESPONSE_FILE="$(mktemp)"

echo "================================================"
echo "Run Alembic Migrations via Lambda"
echo "Function   : ${FUNCTION_NAME}"
echo "================================================"

# Ensure we always restore the original handler on exit
cleanup() {
  echo ""
  echo "▶ Restoring original handler (${ORIGINAL_HANDLER})..."
  aws lambda update-function-configuration \
    --function-name "${FUNCTION_NAME}" \
    --handler "${ORIGINAL_HANDLER}" \
    --no-cli-pager \
    --query 'Handler' --output text
  aws lambda wait function-updated \
    --function-name "${FUNCTION_NAME}" \
    --no-cli-pager
  rm -f "${RESPONSE_FILE}"
  echo "✓ Handler restored"
}
trap cleanup EXIT

# Swap to migration handler
echo ""
echo "▶ Swapping handler to ${MIGRATION_HANDLER}..."
aws lambda update-function-configuration \
  --function-name "${FUNCTION_NAME}" \
  --handler "${MIGRATION_HANDLER}" \
  --no-cli-pager \
  --query 'Handler' --output text

aws lambda wait function-updated \
  --function-name "${FUNCTION_NAME}" \
  --no-cli-pager

# Invoke synchronously (RequestResponse) — Lambda must complete within 30s timeout
echo ""
echo "▶ Invoking migration Lambda..."
aws lambda invoke \
  --function-name "${FUNCTION_NAME}" \
  --payload '{"action":"migrate"}' \
  --cli-binary-format raw-in-base64-out \
  --no-cli-pager \
  "${RESPONSE_FILE}"

echo ""
echo "▶ Migration response:"
cat "${RESPONSE_FILE}"
echo ""

# Check for error in response
STATUS=$(python3 -c "import json,sys; d=json.load(open('${RESPONSE_FILE}')); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")
if [ "${STATUS}" != "success" ]; then
  echo ""
  echo "⚠️  Migration reported non-success status: ${STATUS}"
  echo "   Check CloudWatch logs: /aws/lambda/${FUNCTION_NAME}"
  exit 1
fi

echo ""
echo "================================================"
echo "✓ Migrations complete"
echo "================================================"
