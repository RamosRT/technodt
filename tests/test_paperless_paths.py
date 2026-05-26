from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.paperless_paths import build_archive_path_from_metadata
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
