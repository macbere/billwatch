import unittest

from billwatch import EvidenceLedger, UserContext, Source, SourceType


class TestUserContextSeparation(unittest.TestCase):
    """Test A -- UserContext cannot be treated as Evidence (Gate 2)."""

    def test_add_source_rejects_user_context(self):
        ledger = EvidenceLedger()
        uc = UserContext(
            investigation_id="inv-1",
            stated_concern_text="I know the hospital overcharged me.",
        )
        with self.assertRaises(TypeError):
            ledger.add_source(uc)  # type: ignore[arg-type]

    def test_add_document_rejects_user_context(self):
        ledger = EvidenceLedger()
        uc = UserContext(investigation_id="inv-1", stated_concern_text="This is fraud.")
        with self.assertRaises(TypeError):
            ledger.add_document(uc)  # type: ignore[arg-type]

    def test_add_source_rejects_non_source_generally(self):
        ledger = EvidenceLedger()
        with self.assertRaises(TypeError):
            ledger.add_source("not a source at all")  # type: ignore[arg-type]

    def test_legitimate_source_is_accepted(self):
        ledger = EvidenceLedger()
        src = Source(source_type=SourceType.CMS_NCCI, reference="NCCI 45378/45380")
        ledger.add_source(src)
        self.assertIn(src, ledger.sources)

    def test_user_context_has_no_shared_base_with_source(self):
        # Structural check: UserContext and Source share no base class,
        # so isinstance-based confusion between them is not possible.
        self.assertFalse(issubclass(UserContext, Source))
        self.assertFalse(issubclass(Source, UserContext))


if __name__ == "__main__":
    unittest.main()
