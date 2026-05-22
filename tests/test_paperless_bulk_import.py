import importlib.util
from pathlib import Path


def _load_script_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "paperless_bulk_import.py"
    spec = importlib.util.spec_from_file_location("paperless_bulk_import", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bulk_import = _load_script_module()


def test_build_archive_path_from_media_filename_for_1c_alias_root():
    path = bulk_import.build_archive_path(
        {},
        {
            "has_archive_version": False,
            "media_filename": "2026/03/02.03.2026 УПД № УТ-1566 ООО -Камский Бекон-.pdf",
            "archive_media_filename": None,
        },
        onec_originals_unc_root=r"\\kaz-pc036\Техно-Архив",
        onec_archive_unc_root="",
        replace_unc_from="",
        replace_unc_to="",
    )

    assert path == r"\\kaz-pc036\Техно-Архив\2026\03\02.03.2026 УПД № УТ-1566 ООО -Камский Бекон-.pdf"


def test_build_archive_path_replaces_existing_paperless_unc_prefix():
    path = bulk_import.build_archive_path(
        {
            "archive_path": (
                r"\\paperless-server\paperless-media\documents\originals"
                r"\2026\03\02.03.2026 УПД № УТ-1566 ООО -Камский Бекон-.pdf"
            )
        },
        None,
        onec_originals_unc_root="",
        onec_archive_unc_root="",
        replace_unc_from=r"\\paperless-server\paperless-media\documents\originals",
        replace_unc_to=r"\\kaz-pc036\Техно-Архив",
    )

    assert path == r"\\kaz-pc036\Техно-Архив\2026\03\02.03.2026 УПД № УТ-1566 ООО -Камский Бекон-.pdf"


def test_build_event_includes_archive_path_from_metadata():
    event = bulk_import.build_event(
        {
            "id": 1887,
            "title": "16.02.2026 УПД № УТ-1076 ТАТХИМФАРМПРЕПАРАТЫ АО",
            "document_type": 1,
            "created": "2026-02-16",
            "correspondent": 2,
            "original_file_name": "Untitled - 0126.pdf",
        },
        paperless_url="http://localhost:8000",
        type_map={1: "УПД"},
        correspondent_map={2: "ТАТХИМФАРМПРЕПАРАТЫ АО"},
        metadata={
            "has_archive_version": False,
            "media_filename": "2026/февр./УПД/16.02.2026 УПД № УТ-1076 ТАТХИМФАРМПРЕПАРАТЫ АО.pdf",
        },
        onec_originals_unc_root=r"\\kaz-pc036\Техно-Архив",
    )

    assert event["document_id"] == 1887
    assert event["doc_type"] == "УПД"
    assert event["correspondent"] == "ТАТХИМФАРМПРЕПАРАТЫ АО"
    assert event["download_url"] == "http://localhost:8000/api/documents/1887/download/"
    assert event["archive_path"] == (
        r"\\kaz-pc036\Техно-Архив"
        r"\2026\февр.\УПД\16.02.2026 УПД № УТ-1076 ТАТХИМФАРМПРЕПАРАТЫ АО.pdf"
    )
