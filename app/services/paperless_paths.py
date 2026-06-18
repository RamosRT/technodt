"""UNC paths for 1C storage links from Paperless document metadata."""

from __future__ import annotations

from pathlib import PureWindowsPath
from typing import Any


def normalize_unc_root(value: str) -> str:
    return value.replace("/", "\\").rstrip("\\")


def join_unc(root: str, relative_path: str | None) -> str:
    if not root or not relative_path:
        return ""
    return str(
        PureWindowsPath(normalize_unc_root(root))
        / str(relative_path).replace("/", "\\").lstrip("\\")
    )


def build_archive_path_from_metadata(
    metadata: dict[str, Any],
    *,
    originals_unc_root: str,
    archive_unc_root: str = "",
) -> str:
    """Build kzvСсылкаНаКопию from Paperless metadata.media_filename (or archive copy)."""
    archive_root = archive_unc_root or originals_unc_root
    if metadata.get("has_archive_version") and metadata.get("archive_media_filename"):
        return join_unc(archive_root, str(metadata["archive_media_filename"]))
    return join_unc(originals_unc_root, metadata.get("media_filename"))


def is_merged_pending(
    *,
    original_filename: str | None = None,
    archive_path: str | None = None,
    file_name: str | None = None,
) -> bool:
    """True when Paperless bulk_edit merge metadata is not yet safe for 1C storage link."""
    orig = (original_filename or "").strip().casefold()
    if orig.endswith("_merged.pdf"):
        return True
    for value in (archive_path, file_name):
        if value and "(merged)" in value.casefold():
            return True
    return False
