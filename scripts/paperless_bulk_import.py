#!/usr/bin/env python3
"""
One-shot backfill: imports existing Paperless documents into Konvert-track.

Usage:
    python scripts/paperless_bulk_import.py \
        --paperless-url http://paperless-host:8000 \
        --paperless-token <PAPERLESS_API_TOKEN> \
        --konvertrek-url http://10.60.6.11:8080 \
        --konvertrek-key <PAPERLESS_WEBHOOK_API_KEY>

Run with --dry-run first to inspect document type names and invoice counts
without sending anything to Konvert-track.
"""

import argparse
import os
import time
from collections import Counter
from pathlib import PureWindowsPath
from typing import Any

import httpx

DEFAULT_INVOICE_TYPES = ("упд", "укд", "упд/укд")
DEFAULT_BATCH_SIZE = 50
PAGE_SIZE = 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paperless-url", required=True)
    parser.add_argument("--paperless-token", required=True)
    parser.add_argument("--konvertrek-url", required=True)
    parser.add_argument("--konvertrek-key", required=True)
    parser.add_argument(
        "--onec-originals-unc-root",
        default=os.getenv("PAPERLESS_ONEC_ORIGINALS_UNC_ROOT", ""),
        help=(
            "UNC root to store in 1C for Paperless originals, e.g. "
            r"\\kaz-pc036\Техно-Архив. Can also be set via "
            "PAPERLESS_ONEC_ORIGINALS_UNC_ROOT."
        ),
    )
    parser.add_argument(
        "--onec-archive-unc-root",
        default=os.getenv("PAPERLESS_ONEC_ARCHIVE_UNC_ROOT", ""),
        help=(
            "UNC root to store in 1C for Paperless archive files. Defaults to "
            "--onec-originals-unc-root. Can also be set via "
            "PAPERLESS_ONEC_ARCHIVE_UNC_ROOT."
        ),
    )
    parser.add_argument(
        "--replace-unc-from",
        default=os.getenv("PAPERLESS_REPLACE_UNC_FROM", ""),
        help=(
            "Optional UNC prefix to replace when Paperless already provides archive_path, "
            r"e.g. \\paperless-server\paperless-media\documents\originals."
        ),
    )
    parser.add_argument(
        "--replace-unc-to",
        default=os.getenv("PAPERLESS_REPLACE_UNC_TO", ""),
        help=(
            "Replacement UNC prefix for --replace-unc-from, e.g. "
            r"\\kaz-pc036\Техно-Архив."
        ),
    )
    parser.add_argument(
        "--invoice-type",
        action="append",
        dest="invoice_types",
        help=(
            "Paperless document type name to import. Can be passed multiple times. "
            "Defaults to: упд, укд, упд/укд."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true", help="fetch only, do not send")
    return parser.parse_args()


def _normalized_types(args: argparse.Namespace) -> set[str]:
    raw_types = args.invoice_types or list(DEFAULT_INVOICE_TYPES)
    return {item.strip().lower() for item in raw_types if item.strip()}


def _paperless_client(base_url: str, token: str) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={"Authorization": f"Token {token}"},
        timeout=30,
    )


def _konvertrek_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url.rstrip("/"), timeout=60)


def fetch_all_paginated(client: httpx.Client, path: str) -> list[dict[str, Any]]:
    page = 1
    items: list[dict[str, Any]] = []
    while True:
        resp = client.get(path, params={"page": page, "page_size": PAGE_SIZE})
        resp.raise_for_status()
        data = resp.json()
        items.extend(data.get("results", []))
        if not data.get("next"):
            break
        page += 1
    return items


def fetch_document_types(client: httpx.Client) -> dict[int, str]:
    return {
        int(item["id"]): str(item["name"])
        for item in fetch_all_paginated(client, "/api/document_types/")
        if item.get("id") is not None
    }


def fetch_correspondents(client: httpx.Client) -> dict[int, str]:
    try:
        return {
            int(item["id"]): str(item["name"])
            for item in fetch_all_paginated(client, "/api/correspondents/")
            if item.get("id") is not None
        }
    except httpx.HTTPError as exc:
        print(f"Warning: cannot fetch correspondents: {exc}")
        return {}


def fetch_documents_page(client: httpx.Client, page: int) -> dict[str, Any]:
    resp = client.get(
        "/api/documents/",
        params={"page": page, "page_size": PAGE_SIZE, "ordering": "-created"},
    )
    resp.raise_for_status()
    return resp.json()


def fetch_document_metadata(client: httpx.Client, doc_id: int) -> dict[str, Any]:
    resp = client.get(f"/api/documents/{doc_id}/metadata/")
    resp.raise_for_status()
    return resp.json()


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def is_invoice(
    doc: dict[str, Any],
    type_map: dict[int, str],
    invoice_types: set[str],
) -> bool:
    type_id = _int_or_none(doc.get("document_type"))
    if type_id is None:
        return False
    type_name = type_map.get(type_id, "").strip().lower()
    return type_name in invoice_types


def _correspondent_name(
    doc: dict[str, Any],
    correspondent_map: dict[int, str],
) -> str:
    raw_name = doc.get("correspondent_name") or doc.get("__correspondent__")
    if raw_name:
        return str(raw_name)
    correspondent_id = doc.get("correspondent")
    if correspondent_id is None:
        return ""
    try:
        return correspondent_map.get(int(correspondent_id), "")
    except (TypeError, ValueError):
        return ""


def _normalize_unc_prefix(value: str) -> str:
    return value.replace("/", "\\").rstrip("\\")


def _join_unc(root: str, relative_path: str | None) -> str:
    if not root or not relative_path:
        return ""
    normalized_root = _normalize_unc_prefix(root)
    normalized_relative = str(relative_path).replace("/", "\\").lstrip("\\")
    return str(PureWindowsPath(normalized_root) / normalized_relative)


def _replace_unc_prefix(path: str, old_prefix: str, new_prefix: str) -> str:
    if not path or not old_prefix or not new_prefix:
        return path
    normalized_path = path.replace("/", "\\")
    normalized_old = _normalize_unc_prefix(old_prefix)
    normalized_new = _normalize_unc_prefix(new_prefix)
    if normalized_path.casefold() == normalized_old.casefold():
        return normalized_new
    prefix = normalized_old + "\\"
    if normalized_path.casefold().startswith(prefix.casefold()):
        return normalized_new + "\\" + normalized_path[len(prefix) :]
    return path


def build_archive_path(
    doc: dict[str, Any],
    metadata: dict[str, Any] | None,
    *,
    onec_originals_unc_root: str,
    onec_archive_unc_root: str,
    replace_unc_from: str,
    replace_unc_to: str,
) -> str:
    raw_archive_path = str(doc.get("archive_path") or "").strip()
    if raw_archive_path:
        return _replace_unc_prefix(raw_archive_path, replace_unc_from, replace_unc_to)

    if not metadata:
        return ""

    archive_root = onec_archive_unc_root or onec_originals_unc_root
    if metadata.get("has_archive_version") and metadata.get("archive_media_filename"):
        return _join_unc(archive_root, str(metadata["archive_media_filename"]))

    return _join_unc(onec_originals_unc_root, metadata.get("media_filename"))


def build_event(
    doc: dict[str, Any],
    *,
    paperless_url: str,
    type_map: dict[int, str],
    correspondent_map: dict[int, str],
    metadata: dict[str, Any] | None = None,
    onec_originals_unc_root: str = "",
    onec_archive_unc_root: str = "",
    replace_unc_from: str = "",
    replace_unc_to: str = "",
) -> dict[str, Any]:
    type_id = _int_or_none(doc.get("document_type"))
    doc_id = doc.get("id")
    archive_path = build_archive_path(
        doc,
        metadata,
        onec_originals_unc_root=onec_originals_unc_root,
        onec_archive_unc_root=onec_archive_unc_root,
        replace_unc_from=replace_unc_from,
        replace_unc_to=replace_unc_to,
    )
    return {
        "document_id": doc_id,
        "file_name": doc.get("title", "") or "",
        "doc_type": type_map.get(type_id, "") if type_id is not None else "",
        "created": doc.get("created", "") or "",
        "correspondent": _correspondent_name(doc, correspondent_map),
        "download_url": (
            f"{paperless_url.rstrip('/')}/api/documents/{doc_id}/download/"
            if doc_id is not None
            else ""
        ),
        "original_filename": doc.get("original_file_name", "") or "",
        "archive_path": archive_path,
    }


def send_batch(
    client: httpx.Client,
    api_key: str,
    batch: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    resp = client.post(
        "/api/webhooks/paperless/batch",
        json=batch,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def summarize_results(results: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in results:
        result = item.get("result") if isinstance(item, dict) else None
        status = result.get("status") if isinstance(result, dict) else "unknown"
        counts[str(status)] += 1
    return counts


def print_batch_result(batch_len: int, counts: Counter[str]) -> None:
    summary = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    print(f"  Sent batch of {batch_len}: {summary or 'no results'}")


def main() -> None:
    args = parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1")

    invoice_types = _normalized_types(args)
    pl_client = _paperless_client(args.paperless_url, args.paperless_token)
    kr_client = _konvertrek_client(args.konvertrek_url)

    print("Fetching Paperless dictionaries...")
    type_map = fetch_document_types(pl_client)
    correspondent_map = fetch_correspondents(pl_client)
    type_counts: Counter[str] = Counter(type_map.values())
    print(f"  Document types: {dict(sorted(type_counts.items()))}")
    print(f"  Invoice types selected: {sorted(invoice_types)}")
    print(f"  Correspondents cached: {len(correspondent_map)}")
    if args.onec_originals_unc_root:
        print(f"  1C originals UNC root: {args.onec_originals_unc_root}")
    else:
        print("  Warning: no 1C originals UNC root configured; archive_path will be empty")
    if args.onec_archive_unc_root:
        print(f"  1C archive UNC root: {args.onec_archive_unc_root}")
    if args.replace_unc_from and args.replace_unc_to:
        print(f"  UNC replacement: {args.replace_unc_from} -> {args.replace_unc_to}")

    page = 1
    total_fetched = 0
    total_matched_type = 0
    total_with_archive_path = 0
    total_sent = 0
    result_counts: Counter[str] = Counter()
    batch: list[dict[str, Any]] = []

    while True:
        data = fetch_documents_page(pl_client, page)
        docs = data.get("results", [])
        if not docs:
            break

        for doc in docs:
            if not is_invoice(doc, type_map, invoice_types):
                continue
            metadata: dict[str, Any] | None = None
            doc_id = _int_or_none(doc.get("id"))
            if doc_id is not None:
                metadata = fetch_document_metadata(pl_client, doc_id)
            event = build_event(
                doc,
                paperless_url=args.paperless_url,
                type_map=type_map,
                correspondent_map=correspondent_map,
                metadata=metadata,
                onec_originals_unc_root=args.onec_originals_unc_root,
                onec_archive_unc_root=args.onec_archive_unc_root,
                replace_unc_from=args.replace_unc_from,
                replace_unc_to=args.replace_unc_to,
            )
            if event.get("archive_path"):
                total_with_archive_path += 1
            batch.append(
                event
            )
            total_matched_type += 1

        total_fetched += len(docs)

        if len(batch) >= args.batch_size:
            if args.dry_run:
                print(f"  [dry-run] would send {len(batch)} events")
            else:
                results = send_batch(kr_client, args.konvertrek_key, batch)
                counts = summarize_results(results)
                result_counts.update(counts)
                print_batch_result(len(batch), counts)
                total_sent += len(batch)
                time.sleep(0.5)
            batch = []

        print(
            f"  Page {page}: {len(docs)} docs, "
            f"{total_fetched} fetched, {total_matched_type} invoice-type matches"
        )

        if not data.get("next"):
            break
        page += 1

    if batch:
        if args.dry_run:
            print(f"  [dry-run] would send {len(batch)} events")
        else:
            results = send_batch(kr_client, args.konvertrek_key, batch)
            counts = summarize_results(results)
            result_counts.update(counts)
            print_batch_result(len(batch), counts)
            total_sent += len(batch)

    print(
        "\nDone. "
        f"Fetched={total_fetched}, invoice_type_matches={total_matched_type}, sent={total_sent}"
    )
    print(f"Events with archive_path={total_with_archive_path}")
    if result_counts:
        print("Result statuses:", dict(sorted(result_counts.items())))


if __name__ == "__main__":
    main()
