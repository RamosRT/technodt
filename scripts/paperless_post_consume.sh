#!/usr/bin/env bash
# Paperless-ngx post-consumption hook for Конверт-трек.
# Deploy on the Paperless server. Set in paperless.conf:
#   PAPERLESS_POST_CONSUME_SCRIPT=/opt/scripts/konvertrek_post_consume.sh
# Set environment variables:
#   KONVERTREK_URL=http://10.60.6.11:8080
#   KONVERTREK_API_KEY=<value from .env PAPERLESS_WEBHOOK_API_KEY>

set -euo pipefail

KONVERTREK_URL="${KONVERTREK_URL:-http://10.60.6.11:8080}"
KONVERTREK_API_KEY="${KONVERTREK_API_KEY:-}"

# Build JSON payload from Paperless env vars (always present after consumption)
payload=$(printf '{
  "document_id": %s,
  "file_name": %s,
  "doc_type": %s,
  "created": %s,
  "correspondent": %s,
  "download_url": %s,
  "source_path": %s,
  "original_filename": %s
}' \
  "${DOCUMENT_ID:-0}" \
  "\"${DOCUMENT_FILE_NAME:-}\"" \
  "\"${DOCUMENT_TYPE:-}\"" \
  "\"${DOCUMENT_CREATED:-}\"" \
  "\"${DOCUMENT_CORRESPONDENT:-}\"" \
  "\"${DOCUMENT_DOWNLOAD_URL:-}\"" \
  "\"${DOCUMENT_SOURCE_PATH:-}\"" \
  "\"${DOCUMENT_ORIGINAL_FILENAME:-}\""
)

curl -sf \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${KONVERTREK_API_KEY}" \
  --data "$payload" \
  "${KONVERTREK_URL}/api/webhooks/paperless" \
  || echo "[konvertrek] webhook call failed (non-fatal)" >&2

exit 0
