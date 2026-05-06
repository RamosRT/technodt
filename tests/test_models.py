def test_all_models_registered():
    from app.models import (
        Base,
        EnvelopeStatus,
    )
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {
        "branches",
        "signers",
        "envelopes",
        "envelope_documents",
        "audit_log",
        "operators",
        "printers",
        "system_settings",
        "onec_mark_logs",
    }
    assert {s.value for s in EnvelopeStatus} == {"draft", "sealed", "verified", "verified_with_discrepancy"}
