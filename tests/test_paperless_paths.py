from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.paperless_paths import build_archive_path_from_metadata, is_merged_pending
from app.services.paperless_tag_sync import resolve_archive_path_from_paperless


def test_build_archive_path_egida_example():
    path = build_archive_path_from_metadata(
        {
            "has_archive_version": False,
            "media_filename": "2026/04/30.04.2026 УПД № УТ-3727 Эгида+_05.pdf",
        },
        originals_unc_root=r"\\kaz-pc036\Техно-Архив",
    )
    assert path == r"\\kaz-pc036\Техно-Архив\2026\04\30.04.2026 УПД № УТ-3727 Эгида+_05.pdf"


@pytest.mark.asyncio
async def test_resolve_archive_path_fetches_metadata():
    client = AsyncMock()
    client.fetch_metadata = AsyncMock(
        return_value={
            "has_archive_version": False,
            "media_filename": "2026/04/30.04.2026 УПД № УТ-3727 Эгида+_05.pdf",
        }
    )
    client.aclose = AsyncMock()

    settings = SimpleNamespace(
        paperless_api_url="http://paperless",
        paperless_api_token="token",
        paperless_onec_originals_unc_root=r"\\kaz-pc036\Техно-Архив",
        paperless_onec_archive_unc_root="",
    )

    path = await resolve_archive_path_from_paperless(29858, settings, client=client)

    assert path == r"\\kaz-pc036\Техно-Архив\2026\04\30.04.2026 УПД № УТ-3727 Эгида+_05.pdf"
    client.fetch_metadata.assert_awaited_once_with(29858)


def test_is_merged_pending_by_original_filename_without_archive_path():
    assert is_merged_pending(original_filename="30075_29553_merged.pdf") is True


def test_is_merged_pending_false_when_archive_path_final_despite_merged_original():
    assert is_merged_pending(
        original_filename="29433_29432_merged.pdf",
        archive_path=(
            r"\\kaz-pc036\Техно-Архив\2026\04\20.04.2026 УПД № УТ-3257 "
            r"Общество с ограниченной ответственностью Специализированный застройщик -ДОМКОР-_02.pdf"
        ),
        file_name="20.04.2026 УПД № УТ-3257 Общество с ограниченной ответственностью Специализированный застройщик -ДОМКОР-",
    ) is False


def test_is_merged_pending_by_archive_path():
    assert is_merged_pending(
        archive_path=r"\\kaz-pc036\Техно-Архив\2025\11\doc (merged).pdf",
    ) is True


def test_is_merged_pending_false_for_final_path():
    assert is_merged_pending(
        original_filename="2025/11/25.11.2025 УПД № УТ-13995 Глобус_02.pdf",
        archive_path=r"\\kaz-pc036\Техно-Архив\2025\11\25.11.2025 УПД № УТ-13995 Глобус_02.pdf",
    ) is False
