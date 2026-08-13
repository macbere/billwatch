"""
Build 4A: Extraction Integration tests.

Tests billwatch/extraction_integration.py ONLY. All tests use
MockLLMProvider -- Gemini credentials are never required and no real
network call is ever made anywhere in this file.
"""

import json
import unittest

from billwatch import Document, Investigation, UserContext
from billwatch.llm_provider import MockLLMProvider, LLMProviderError
from billwatch.extraction_integration import (
    ExtractionIntegrationError,
    ExtractionIntegrationResult,
    integrate_extraction,
)


def _valid_response_json(document, facts=None):
    return json.dumps({
        "document_id": document.id,
        "extracted_facts": facts if facts is not None else [],
    })


def _new_investigation_with_document(raw_text):
    inv = Investigation()
    doc = Document(doc_type="bill", raw_text=raw_text)
    inv.ledger.add_document(doc)
    return inv, doc


# ---------------------------------------------------------------------
# GROUP A -- Valid extraction reaches EvidenceLedger
# ---------------------------------------------------------------------
class TestValidExtractionReachesLedger(unittest.TestCase):

    def test_accepted_facts_are_added_to_the_ledger(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.00.")
        facts = [{"fact_type": "code", "value": "99213", "source_span": "CPT 99213"}]
        provider = MockLLMProvider(fixed_response=_valid_response_json(doc, facts))

        result = integrate_extraction(inv, doc, provider)

        self.assertTrue(result.success)
        self.assertEqual(len(result.fact_ids_added), 1)
        self.assertEqual(len(inv.ledger.facts), 1)
        self.assertEqual(inv.ledger.facts[0].id, result.fact_ids_added[0])
        self.assertEqual(inv.ledger.facts[0].document_id, doc.id)
        self.assertEqual(inv.ledger.facts[0].fact_type, "code")

    def test_multiple_facts_all_reach_the_ledger(self):
        inv, doc = _new_investigation_with_document(
            "CPT 99213 billed for $250.00 on 2026-01-15."
        )
        facts = [
            {"fact_type": "code", "value": "99213", "source_span": "CPT 99213"},
            {"fact_type": "amount", "value": "250.00", "source_span": "$250.00"},
            {"fact_type": "date", "value": "2026-01-15", "source_span": "2026-01-15"},
        ]
        provider = MockLLMProvider(fixed_response=_valid_response_json(doc, facts))

        result = integrate_extraction(inv, doc, provider)

        self.assertTrue(result.success)
        self.assertEqual(len(result.fact_ids_added), 3)
        self.assertEqual(len(inv.ledger.facts), 3)

    def test_clean_bill_zero_facts_is_a_success_with_nothing_added(self):
        inv, doc = _new_investigation_with_document("Nothing billable here.")
        provider = MockLLMProvider(fixed_response=_valid_response_json(doc, []))

        result = integrate_extraction(inv, doc, provider)

        self.assertTrue(result.success)
        self.assertEqual(result.fact_ids_added, ())
        self.assertEqual(len(inv.ledger.facts), 0)

    def test_result_reports_rejected_fact_count_and_reasons(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.00.")
        facts = [
            {"fact_type": "code", "value": "99213", "source_span": "CPT 99213"},
            {"fact_type": "amount", "value": "9999", "source_span": "totally invented span"},
        ]
        provider = MockLLMProvider(fixed_response=_valid_response_json(doc, facts))

        result = integrate_extraction(inv, doc, provider)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.facts), 1)  # only the real one
        self.assertEqual(result.rejected_fact_count, 1)
        self.assertEqual(len(result.rejected_reasons), 1)


# ---------------------------------------------------------------------
# GROUP B -- Malformed / empty model output safely rejected
# ---------------------------------------------------------------------
class TestMalformedOutputSafelyRejected(unittest.TestCase):

    def test_malformed_json_rejected_nothing_added_to_ledger(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        provider = MockLLMProvider(fixed_response="not json {{{")

        result = integrate_extraction(inv, doc, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertEqual(len(inv.ledger.facts), 0)

    def test_empty_string_response_rejected(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        provider = MockLLMProvider(fixed_response="")

        result = integrate_extraction(inv, doc, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertEqual(len(inv.ledger.facts), 0)

    def test_truncated_json_rejected(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        provider = MockLLMProvider(fixed_response='{"document_id": "abc", "extracted_fa')

        result = integrate_extraction(inv, doc, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertEqual(len(inv.ledger.facts), 0)


# ---------------------------------------------------------------------
# GROUP C -- Invalid/unknown fields rejected individually
# ---------------------------------------------------------------------
class TestInvalidFieldsRejected(unittest.TestCase):

    def test_unknown_fact_type_rejected_not_added_to_ledger(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        facts = [{"fact_type": "diagnosis_guess", "value": "flu", "source_span": "CPT 99213"}]
        provider = MockLLMProvider(fixed_response=_valid_response_json(doc, facts))

        result = integrate_extraction(inv, doc, provider)

        self.assertTrue(result.success)  # candidate as a whole still valid
        self.assertEqual(len(inv.ledger.facts), 0)
        self.assertEqual(result.rejected_fact_count, 1)

    def test_missing_required_field_rejects_whole_candidate(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        raw = json.dumps({"extracted_facts": []})  # missing document_id
        provider = MockLLMProvider(fixed_response=raw)

        result = integrate_extraction(inv, doc, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertEqual(len(inv.ledger.facts), 0)

    def test_wrong_type_for_extracted_facts_rejects_whole_candidate(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        raw = json.dumps({"document_id": doc.id, "extracted_facts": "not a list"})
        provider = MockLLMProvider(fixed_response=raw)

        result = integrate_extraction(inv, doc, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertEqual(len(inv.ledger.facts), 0)


# ---------------------------------------------------------------------
# GROUP D -- Recursive domain-decision field rejection
# ---------------------------------------------------------------------
class TestDomainDecisionFieldsRejected(unittest.TestCase):

    def test_final_status_top_level_rejects_whole_candidate(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        raw = json.dumps({
            "document_id": doc.id,
            "extracted_facts": [{"fact_type": "code", "value": "99213", "source_span": "CPT 99213"}],
            "final_status": "SUPPORTED_DISCREPANCY",
        })
        provider = MockLLMProvider(fixed_response=raw)

        result = integrate_extraction(inv, doc, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertEqual(len(inv.ledger.facts), 0)

    def test_case_scope_nested_in_a_fact_rejects_whole_candidate(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        raw = json.dumps({
            "document_id": doc.id,
            "extracted_facts": [
                {"fact_type": "code", "value": "99213", "source_span": "CPT 99213",
                 "case_scope": "medicare"}
            ],
        })
        provider = MockLLMProvider(fixed_response=raw)

        result = integrate_extraction(inv, doc, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertEqual(len(inv.ledger.facts), 0)

    def test_appeal_eligible_anywhere_rejects_whole_candidate(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        raw = json.dumps({
            "document_id": doc.id,
            "extracted_facts": [{"fact_type": "code", "value": "99213", "source_span": "CPT 99213"}],
            "appeal_eligible": True,
        })
        provider = MockLLMProvider(fixed_response=raw)

        result = integrate_extraction(inv, doc, provider)

        self.assertFalse(result.success)
        self.assertEqual(len(inv.ledger.facts), 0)


# ---------------------------------------------------------------------
# GROUP E -- Hallucinated source_span rejected
# ---------------------------------------------------------------------
class TestHallucinatedSourceSpanRejected(unittest.TestCase):

    def test_hallucinated_span_rejected_valid_facts_still_succeed(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.00.")
        facts = [
            {"fact_type": "code", "value": "99213", "source_span": "CPT 99213"},
            {"fact_type": "code", "value": "99214", "source_span": "CPT 99214 invented"},
        ]
        provider = MockLLMProvider(fixed_response=_valid_response_json(doc, facts))

        result = integrate_extraction(inv, doc, provider)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.facts), 1)
        self.assertEqual(inv.ledger.facts[0].value, "99213")
        self.assertEqual(result.rejected_fact_count, 1)

    def test_high_confidence_does_not_rescue_hallucinated_span(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.00.")
        facts = [{
            "fact_type": "amount", "value": "9999.99",
            "source_span": "fabricated span", "confidence": "100% certain",
        }]
        provider = MockLLMProvider(fixed_response=_valid_response_json(doc, facts))

        result = integrate_extraction(inv, doc, provider)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.facts), 0)
        self.assertEqual(result.rejected_fact_count, 1)


# ---------------------------------------------------------------------
# GROUP F -- UserContext contamination rejected (Gate 2, re-enforced here)
# ---------------------------------------------------------------------
class TestUserContextContaminationRejected(unittest.TestCase):

    def test_usercontext_passed_as_document_raises_before_any_provider_call(self):
        inv = Investigation()
        uc = UserContext(
            investigation_id=inv.investigation_id,
            stated_concern_text="I know the hospital overcharged me.",
        )
        calls = []
        provider = MockLLMProvider(response_fn=lambda s, u: calls.append(1) or "{}")

        with self.assertRaises(ExtractionIntegrationError):
            integrate_extraction(inv, uc, provider)  # type: ignore[arg-type]

        self.assertEqual(calls, [])  # provider never invoked
        self.assertEqual(len(inv.ledger.facts), 0)

    def test_non_document_object_also_rejected(self):
        inv = Investigation()
        provider = MockLLMProvider(fixed_response="{}")
        with self.assertRaises(ExtractionIntegrationError):
            integrate_extraction(inv, "not a document at all", provider)  # type: ignore[arg-type]


# ---------------------------------------------------------------------
# GROUP G -- Unregistered document handled safely
# ---------------------------------------------------------------------
class TestUnregisteredDocumentHandledSafely(unittest.TestCase):

    def test_document_never_added_to_ledger_fails_at_registration_stage(self):
        inv = Investigation()
        orphan_doc = Document(doc_type="bill", raw_text="CPT 99213 billed for $250.")
        # Deliberately NOT calling inv.ledger.add_document(orphan_doc).
        calls = []
        provider = MockLLMProvider(response_fn=lambda s, u: calls.append(1) or "{}")

        result = integrate_extraction(inv, orphan_doc, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "registration")
        self.assertEqual(calls, [])  # provider never invoked -- fails before any LLM call
        self.assertEqual(len(inv.ledger.facts), 0)


# ---------------------------------------------------------------------
# GROUP I -- Provider failure safely propagated
# ---------------------------------------------------------------------
class TestProviderFailureSafelyPropagated(unittest.TestCase):

    def test_provider_failure_reported_not_fabricated(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        provider = MockLLMProvider(raise_error=LLMProviderError("simulated network failure"))

        result = integrate_extraction(inv, doc, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "provider")
        self.assertIn("simulated network failure", result.failure_reason)
        self.assertEqual(len(inv.ledger.facts), 0)

    def test_non_provider_exception_still_propagates_not_swallowed(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        provider = MockLLMProvider(raise_error=RuntimeError("unexpected bug"))
        with self.assertRaises(RuntimeError):
            integrate_extraction(inv, doc, provider)


# ---------------------------------------------------------------------
# GROUP L -- Hard gates remain unchanged through this new integration path
# ---------------------------------------------------------------------
class TestHardGatesUnchangedThroughIntegration(unittest.TestCase):

    def test_integration_never_sets_case_scope(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        facts = [{"fact_type": "code", "value": "99213", "source_span": "CPT 99213"}]
        provider = MockLLMProvider(fixed_response=_valid_response_json(doc, facts))
        integrate_extraction(inv, doc, provider)
        self.assertIsNone(inv.case_scope)

    def test_integration_never_sets_final_status(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        facts = [{"fact_type": "code", "value": "99213", "source_span": "CPT 99213"}]
        provider = MockLLMProvider(fixed_response=_valid_response_json(doc, facts))
        integrate_extraction(inv, doc, provider)
        self.assertIsNone(inv.final_status)

    def test_integration_never_advances_the_state_machine(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        facts = [{"fact_type": "code", "value": "99213", "source_span": "CPT 99213"}]
        provider = MockLLMProvider(fixed_response=_valid_response_json(doc, facts))
        from billwatch import InvestigationState
        integrate_extraction(inv, doc, provider)
        self.assertEqual(inv.state, InvestigationState.INGESTED)

    def test_integration_can_never_enable_appeal(self):
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        facts = [{"fact_type": "code", "value": "99213", "source_span": "CPT 99213"}]
        provider = MockLLMProvider(fixed_response=_valid_response_json(doc, facts))
        integrate_extraction(inv, doc, provider)
        self.assertFalse(inv.can_draft_appeal())

    def test_gate2_add_source_still_rejects_usercontext_after_integration_used(self):
        # Proves this new module hasn't weakened Gate 2's enforcement point
        # for anyone else still using the ledger directly.
        inv, doc = _new_investigation_with_document("CPT 99213 billed for $250.")
        facts = [{"fact_type": "code", "value": "99213", "source_span": "CPT 99213"}]
        provider = MockLLMProvider(fixed_response=_valid_response_json(doc, facts))
        integrate_extraction(inv, doc, provider)

        uc = UserContext(investigation_id=inv.investigation_id, stated_concern_text="x")
        with self.assertRaises(TypeError):
            inv.ledger.add_source(uc)  # type: ignore[arg-type]

    def test_no_provider_class_imported_into_this_test_module(self):
        # Every test in this file uses MockLLMProvider -- confirms neither
        # real provider class was even imported here, structurally
        # guaranteeing no live network path exists in this file.
        import sys
        this_module = sys.modules[__name__]
        self.assertNotIn("GeminiProvider", vars(this_module))
        self.assertNotIn("GenAISDKProvider", vars(this_module))


if __name__ == "__main__":
    unittest.main()
