def test_all_models_registered():
    from app.models import Base, Branch, Signer, Envelope, EnvelopeStatus, EnvelopeDocument, AuditLog
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {"branches", "signers", "envelopes", "envelope_documents", "audit_log"}
    assert {s.value for s in EnvelopeStatus} == {"draft", "sealed", "verified", "verified_with_discrepancy"}
