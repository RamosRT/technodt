#!/usr/bin/env bash
# Paperless-ngx post-consumption hook for Конверт-трек.
# Deploy on the Paperless server. Set in paperless.conf:
#   PAPERLESS_POST_CONSUME_SCRIPT=/opt/scripts/konvertrek_post_consume.sh
# Set environment variables:
#   KONVERTREK_URL=http://10.60.6.11:8080
#   KONVERTREK_API_KEY=<value from .env PAPERLESS_WEBHOOK_API_KEY>
#   KONVERTREK_ONEC_ORIGINALS_UNC_ROOT=\\server\share
# Optional:
#   KONVERTREK_ONEC_ARCHIVE_UNC_ROOT=\\server\archive-share

set -euo pipefail

KONVERTREK_URL="${KONVERTREK_URL:-http://10.60.6.11:8080}"
KONVERTREK_API_KEY="${KONVERTREK_API_KEY:-}"
KONVERTREK_ONEC_ORIGINALS_UNC_ROOT="${KONVERTREK_ONEC_ORIGINALS_UNC_ROOT:-}"
KONVERTREK_ONEC_ARCHIVE_UNC_ROOT="${KONVERTREK_ONEC_ARCHIVE_UNC_ROOT:-}"

# Build JSON payload from Paperless env vars. Python is available in the
# Paperless image and gives us correct JSON escaping for Russian filenames.
payload=$(python - <<'PY'
import json
import os


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value.casefold() in {"none", "null"}:
        return None
    return value


def join_unc(root: str, relative: str) -> str:
    return root.rstrip("\\/") + "\\" + relative.replace("/", "\\").lstrip("\\/")


def onec_path_from_paperless_path(path: str | None) -> str | None:
    path = clean(path)
    if not path:
        return None

    normalized = path.replace("\\", "/")
    markers = (
        ("/documents/archive/", os.getenv("KONVERTREK_ONEC_ARCHIVE_UNC_ROOT") or os.getenv("KONVERTREK_ONEC_ORIGINALS_UNC_ROOT") or ""),
        ("/documents/originals/", os.getenv("KONVERTREK_ONEC_ORIGINALS_UNC_ROOT") or ""),
    )
    for marker, root in markers:
        if marker in normalized and root:
            return join_unc(root, normalized.split(marker, 1)[1])
    return path


def onec_original_path_from_public_filename() -> str | None:
    root = clean(os.getenv("KONVERTREK_ONEC_ORIGINALS_UNC_ROOT"))
    file_name = clean(os.getenv("DOCUMENT_FILE_NAME"))
    created = clean(os.getenv("DOCUMENT_CREATED"))
    if not root or not file_name or not created or len(created) < 7:
        return None
    year = created[0:4]
    month = created[5:7]
    if not year.isdigit() or not month.isdigit():
        return None
    return join_unc(root, f"{year}/{month}/{file_name}")


document_id = os.getenv("DOCUMENT_ID") or "0"
try:
    document_id_value = int(document_id)
except ValueError:
    document_id_value = 0

payload = {
    "document_id": document_id_value,
    "file_name": clean(os.getenv("DOCUMENT_FILE_NAME")),
    "doc_type": clean(os.getenv("DOCUMENT_TYPE")),
    "created": clean(os.getenv("DOCUMENT_CREATED")),
    "correspondent": clean(os.getenv("DOCUMENT_CORRESPONDENT")),
    "download_url": clean(os.getenv("DOCUMENT_DOWNLOAD_URL")),
    "source_path": clean(os.getenv("DOCUMENT_SOURCE_PATH")),
    "archive_path": (
        onec_path_from_paperless_path(os.getenv("DOCUMENT_ARCHIVE_PATH"))
        or onec_original_path_from_public_filename()
    ),
    "original_filename": clean(os.getenv("DOCUMENT_ORIGINAL_FILENAME")),
    "tags": clean(os.getenv("DOCUMENT_TAGS")),
}
print(json.dumps(payload, ensure_ascii=False))
PY
)

curl -sf \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${KONVERTREK_API_KEY}" \
  --data "$payload" \
  "${KONVERTREK_URL}/api/webhooks/paperless" \
  || echo "[konvertrek] webhook call failed (non-fatal)" >&2

exit 0
