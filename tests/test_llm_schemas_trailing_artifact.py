"""
Confirms the shared trailing-JSON-artifact cleanup in
llm_schemas.py::_parse_json_object() (originally added only for the
appeal-drafting contract, then moved here after the SAME empirically-
observed artifact was captured at the hypothesis stage -- see
tests/test_appeal_reliability_retry.py for the original appeal-stage
capture) also protects the extraction, hypothesis, and verification
contracts, since all four funnel through the same shared function.
"""
import json
import unittest

from billwatch import Document
from billwatch.llm_schemas import (
    SchemaValidationError,
    parse_extraction_candidate,
    parse_hypothesis_candidate,
    parse_verification_candidate,
)


class TestTrailingArtifactAcrossAllFourContracts(unittest.TestCase):

    def test_extraction_recovers_from_trailing_newline_and_stray_text(self):
        doc = Document(doc_type="bill", raw_text="CPT 99213 billed.")
        payload = json.dumps({"document_id": doc.id, "extracted_facts": []})
        raw = payload + "\n\nThank you."
        result = parse_extraction_candidate(raw, doc)
        self.assertEqual(result.document_id, doc.id)

    def test_hypothesis_recovers_from_trailing_data(self):
        payload = json.dumps({
            "claim_statement": "x", "explanation_text": "y", "referenced_fact_ids": [],
        })
        raw = payload + "\nExtra stray content"
        result = parse_hypothesis_candidate(raw, known_fact_ids=set())
        self.assertEqual(result.claim_statement, "x")

    def test_verification_recovers_from_trailing_data(self):
        payload = json.dumps({
            "hypothesis_id": "h1", "proposed_source_types": ["CMS_NCCI"],
            "verification_rationale": "check",
        })
        raw = payload + "\n\n"
        result = parse_verification_candidate(raw, known_hypothesis_ids={"h1"})
        self.assertEqual(result.hypothesis_id, "h1")

    def test_genuinely_malformed_json_still_rejected_extraction(self):
        doc = Document(doc_type="bill", raw_text="CPT 99213 billed.")
        with self.assertRaises(SchemaValidationError):
            parse_extraction_candidate("not json {{{", doc)

    def test_genuinely_malformed_json_still_rejected_hypothesis(self):
        with self.assertRaises(SchemaValidationError):
            parse_hypothesis_candidate("not json {{{", known_fact_ids=set())

    def test_genuinely_malformed_json_still_rejected_verification(self):
        with self.assertRaises(SchemaValidationError):
            parse_verification_candidate("not json {{{", known_hypothesis_ids=set())


if __name__ == "__main__":
    unittest.main()
