#!/bin/bash
# Run orphaned watchlist deal cleanup via the API Lambda (VPC access to Aurora).
# Temporarily swaps the Lambda handler, invokes it, then restores the original.
#
# Usage:
#   ./scripts/run-cleanup-lambda.sh [environment] [--execute]
#
# Examples:
#   ./scripts/run-cleanup-lambda.sh prod           # dry-run (default)
#   ./scripts/run-cleanup-lambda.sh prod --execute # actually delete

set -e

ENVIRONMENT="${1:-prod}"
EXECUTE="${2:-}"
FUNCTION_NAME="dealfinder-${ENVIRONMENT}-api"
ORIGINAL_HANDLER="dealfinder.api.main.handler"
CLEANUP_HANDLER="dealfinder.db.cleanup_handler.handler"
RESPONSE_FILE="$(mktemp)"

if [ "${EXECUTE}" = "--execute" ]; then
  PAYLOAD='{"dry_run": false}'
  MODE="LIVE"
else
  PAYLOAD='{"dry_run": true}'
  MODE="DRY RUN"
fi

echo "================================================"
echo "Orphaned Watchlist Deal Cleanup via Lambda"
echo "Function   : ${FUNCTION_NAME}"
echo "Mode       : ${MODE}"
echo "================================================"

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

echo ""
echo "▶ Swapping handler to ${CLEANUP_HANDLER}..."
aws lambda update-function-configuration \
  --function-name "${FUNCTION_NAME}" \
  --handler "${CLEANUP_HANDLER}" \
  --no-cli-pager \
  --query 'Handler' --output text

aws lambda wait function-updated \
  --function-name "${FUNCTION_NAME}" \
  --no-cli-pager

echo ""
echo "▶ Invoking cleanup Lambda  [${MODE}]..."
aws lambda invoke \
  --function-name "${FUNCTION_NAME}" \
  --payload "${PAYLOAD}" \
  --cli-binary-format raw-in-base64-out \
  --no-cli-pager \
  "${RESPONSE_FILE}"

echo ""
echo "▶ Response:"
python3 -c "import json,sys; print(json.dumps(json.load(open('${RESPONSE_FILE}')), indent=2))"
echo ""

STATUS=$(python3 -c "import json,sys; d=json.load(open('${RESPONSE_FILE}')); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")
ERROR_TYPE=$(python3 -c "import json,sys; d=json.load(open('${RESPONSE_FILE}')); print(d.get('errorType',''))" 2>/dev/null || echo "")

if [ -n "${ERROR_TYPE}" ] || [ "${STATUS}" = "error" ]; then
  echo "⚠️  Cleanup failed (${ERROR_TYPE:-unknown error}). Check CloudWatch logs: /aws/lambda/${FUNCTION_NAME}"
  exit 1
fi

echo "================================================"
if [ "${MODE}" = "DRY RUN" ]; then
  echo "✓ Dry run complete. Re-run with --execute to apply."
else
  echo "✓ Cleanup complete."
fi
echo "================================================"
