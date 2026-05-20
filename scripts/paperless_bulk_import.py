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
import time
from collections import Counter
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


def build_event(
    doc: dict[str, Any],
    *,
    paperless_url: str,
    type_map: dict[int, str],
    correspondent_map: dict[int, str],
) -> dict[str, Any]:
    type_id = _int_or_none(doc.get("document_type"))
    doc_id = doc.get("id")
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
        "archive_path": "",
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

    page = 1
    total_fetched = 0
    total_matched_type = 0
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
            batch.append(
                build_event(
                    doc,
                    paperless_url=args.paperless_url,
                    type_map=type_map,
                    correspondent_map=correspondent_map,
                )
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
    if result_counts:
        print("Result statuses:", dict(sorted(result_counts.items())))


if __name__ == "__main__":
    main()
