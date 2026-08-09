import unittest

from billwatch import EvidenceLedger, Source, SourceType, Document


class TestEvidenceImmutabilityStrengthened(unittest.TestCase):
    """
    Build 2, Section 10: closes the gap flagged as a Build 1 risk. Frozen
    dataclasses already block in-place attribute mutation (Build 1); this
    confirms the ledger additionally refuses to accept a second entity
    sharing an existing entity's id, which would otherwise let a caller
    simulate an edit by re-adding under the same identity.
    """

    def test_duplicate_source_id_rejected(self):
        ledger = EvidenceLedger()
        src = Source(source_type=SourceType.CMS_NCCI, reference="original")
        ledger.add_source(src)

        # Construct a "changed" version but force the same id, simulating
        # an attempted same-identity edit.
        import dataclasses
        changed = dataclasses.replace(src, reference="tampered")
        with self.assertRaises(ValueError):
            ledger.add_source(changed)

        # The original, unaltered record is still the only one present.
        self.assertEqual(len(ledger.sources), 1)
        self.assertEqual(ledger.sources[0].reference, "original")

    def test_duplicate_document_id_rejected(self):
        ledger = EvidenceLedger()
        doc = Document(doc_type="bill", raw_text="original text")
        ledger.add_document(doc)

        import dataclasses
        changed = dataclasses.replace(doc, raw_text="tampered text")
        with self.assertRaises(ValueError):
            ledger.add_document(changed)

        self.assertEqual(len(ledger.documents), 1)
        self.assertEqual(ledger.documents[0].raw_text, "original text")

    def test_genuinely_new_entity_with_new_id_is_accepted(self):
        ledger = EvidenceLedger()
        src1 = Source(source_type=SourceType.CMS_NCCI, reference="first")
        src2 = Source(source_type=SourceType.CMS_NCCI, reference="second")  # distinct auto-generated id
        ledger.add_source(src1)
        ledger.add_source(src2)
        self.assertEqual(len(ledger.sources), 2)


if __name__ == "__main__":
    unittest.main()
