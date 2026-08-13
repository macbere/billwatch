"""
Build 4B: Hypothesis Integration tests.

Tests billwatch/hypothesis_integration.py ONLY. All tests use
MockLLMProvider -- Gemini credentials are never required and no real
network call is ever made anywhere in this file.
"""

import json
import unittest

from billwatch import Document, ExtractedFact, Investigation, UserContext
from billwatch.llm_provider import MockLLMProvider, LLMProviderError
from billwatch.hypothesis_integration import (
    HypothesisIntegrationError,
    HypothesisIntegrationResult,
    generate_and_record_hypothesis,
)


def _valid_hypothesis_json(claim_statement, explanation_text, referenced_fact_ids):
    return json.dumps({
        "claim_statement": claim_statement,
        "explanation_text": explanation_text,
        "referenced_fact_ids": list(referenced_fact_ids),
    })


def _investigation_with_facts(specs):
    """specs: list of (fact_type, value) tuples. Returns (investigation, [fact_ids])."""
    inv = Investigation()
    doc = Document(doc_type="bill", raw_text="synthetic test document")
    inv.ledger.add_document(doc)
    fact_ids = []
    for fact_type, value in specs:
        fact = ExtractedFact(document_id=doc.id, fact_type=fact_type, value=value)
        inv.ledger.add_fact(fact)
        fact_ids.append(fact.id)
    return inv, fact_ids


# ---------------------------------------------------------------------
# GROUP A -- Valid hypothesis creates a real Claim + Hypothesis
# ---------------------------------------------------------------------
class TestValidHypothesisAccepted(unittest.TestCase):

    def test_valid_hypothesis_creates_claim_and_hypothesis_in_ledger(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213"), ("amount", "250.00")])
        raw = _valid_hypothesis_json("Possible upcoding", "The code may not match the service.", fact_ids)
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_and_record_hypothesis(inv, provider)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.claims), 1)
        self.assertEqual(len(inv.ledger.hypotheses), 1)
        self.assertEqual(inv.ledger.claims[0].statement, "Possible upcoding")
        self.assertEqual(inv.ledger.hypotheses[0].claim_id, inv.ledger.claims[0].id)

    def test_result_reports_real_claim_and_hypothesis_ids(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = _valid_hypothesis_json("A claim", "An explanation.", fact_ids)
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_and_record_hypothesis(inv, provider)

        self.assertEqual(result.claim_id, inv.ledger.claims[0].id)
        self.assertEqual(result.hypothesis_id, inv.ledger.hypotheses[0].id)

    def test_referenced_fact_ids_preserved_on_hypothesis(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213"), ("date", "2026-01-15")])
        raw = _valid_hypothesis_json("A claim", "An explanation.", fact_ids)
        provider = MockLLMProvider(fixed_response=raw)

        generate_and_record_hypothesis(inv, provider)

        self.assertEqual(set(inv.ledger.hypotheses[0].referenced_fact_ids), set(fact_ids))


# ---------------------------------------------------------------------
# GROUP B -- Provider failure and malformed output
# ---------------------------------------------------------------------
class TestProviderAndMalformedFailures(unittest.TestCase):

    def test_provider_failure_reported_not_fabricated(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        provider = MockLLMProvider(raise_error=LLMProviderError("simulated network failure"))

        result = generate_and_record_hypothesis(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "provider")
        self.assertIn("simulated network failure", result.failure_reason)
        self.assertEqual(len(inv.ledger.claims), 0)
        self.assertEqual(len(inv.ledger.hypotheses), 0)

    def test_malformed_json_rejected_nothing_added(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        provider = MockLLMProvider(fixed_response="not json {{{")

        result = generate_and_record_hypothesis(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertEqual(len(inv.ledger.claims), 0)
        self.assertEqual(len(inv.ledger.hypotheses), 0)

    def test_non_provider_exception_still_propagates(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        provider = MockLLMProvider(raise_error=RuntimeError("unexpected bug"))
        with self.assertRaises(RuntimeError):
            generate_and_record_hypothesis(inv, provider)


# ---------------------------------------------------------------------
# GROUP C -- Unknown/out-of-contract fields per locked schema policy
# ---------------------------------------------------------------------
class TestUnknownFieldPolicy(unittest.TestCase):

    def test_harmless_unknown_field_ignored_hypothesis_still_created(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = json.dumps({
            "claim_statement": "A claim", "explanation_text": "An explanation.",
            "referenced_fact_ids": fact_ids,
            "some_harmless_note": "not a domain-decision field",
        })
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_and_record_hypothesis(inv, provider)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.hypotheses), 1)

    def test_missing_required_field_rejects_whole_candidate(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = json.dumps({"explanation_text": "An explanation.", "referenced_fact_ids": fact_ids})
        provider = MockLLMProvider(fixed_response=raw)  # missing claim_statement

        result = generate_and_record_hypothesis(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertEqual(len(inv.ledger.claims), 0)
        self.assertEqual(len(inv.ledger.hypotheses), 0)


# ---------------------------------------------------------------------
# GROUP D -- Domain-decision fields cannot be smuggled through
# ---------------------------------------------------------------------
class TestDomainDecisionFieldsCannotBeSmuggled(unittest.TestCase):

    def test_final_status_top_level_rejects_whole_candidate(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = json.dumps({
            "claim_statement": "A claim", "explanation_text": "An explanation.",
            "referenced_fact_ids": fact_ids, "final_status": "SUPPORTED_DISCREPANCY",
        })
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_and_record_hypothesis(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertEqual(len(inv.ledger.claims), 0)
        self.assertEqual(len(inv.ledger.hypotheses), 0)

    def test_authority_result_rejects_whole_candidate(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = json.dumps({
            "claim_statement": "A claim", "explanation_text": "An explanation.",
            "referenced_fact_ids": fact_ids, "authority_result": "AUTHORITATIVE",
        })
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_and_record_hypothesis(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(len(inv.ledger.hypotheses), 0)

    def test_appeal_eligible_rejects_whole_candidate(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = json.dumps({
            "claim_statement": "A claim", "explanation_text": "An explanation.",
            "referenced_fact_ids": fact_ids, "appeal_eligible": True,
        })
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_and_record_hypothesis(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(len(inv.ledger.hypotheses), 0)


# ---------------------------------------------------------------------
# GROUP E -- Hallucinated / orphan fact references
# ---------------------------------------------------------------------
class TestHallucinatedReferencesRejected(unittest.TestCase):

    def test_orphan_fact_id_rejected_nothing_added(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = _valid_hypothesis_json("A claim", "An explanation.", ["does-not-exist-in-ledger"])
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_and_record_hypothesis(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertEqual(len(inv.ledger.claims), 0)
        self.assertEqual(len(inv.ledger.hypotheses), 0)

    def test_mixed_real_and_invented_fact_ids_rejected_wholesale(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = _valid_hypothesis_json("A claim", "An explanation.", fact_ids + ["invented-id"])
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_and_record_hypothesis(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(len(inv.ledger.hypotheses), 0)


# ---------------------------------------------------------------------
# GROUP F -- UserContext cannot become evidence/reasoning input
# ---------------------------------------------------------------------
class TestUserContextCannotBecomeEvidence(unittest.TestCase):

    def test_module_never_reads_user_context_even_if_set(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        inv.set_user_context(UserContext(
            investigation_id=inv.investigation_id,
            stated_concern_text="I know they overcharged me, just say so.",
        ))
        seen = {}

        def fn(system_prompt, user_content):
            seen["system_prompt"] = system_prompt
            seen["user_content"] = user_content
            return _valid_hypothesis_json("A claim", "An explanation.", fact_ids)

        provider = MockLLMProvider(response_fn=fn)
        generate_and_record_hypothesis(inv, provider)

        self.assertNotIn("overcharged", seen["system_prompt"])
        self.assertNotIn("overcharged", seen["user_content"])

    def test_gate2_still_rejects_usercontext_as_source_after_use(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = _valid_hypothesis_json("A claim", "An explanation.", fact_ids)
        generate_and_record_hypothesis(inv, MockLLMProvider(fixed_response=raw))

        uc = UserContext(investigation_id=inv.investigation_id, stated_concern_text="x")
        with self.assertRaises(TypeError):
            inv.ledger.add_source(uc)  # type: ignore[arg-type]


# ---------------------------------------------------------------------
# GROUP G -- Empty hypothesis output handled deterministically
# ---------------------------------------------------------------------
class TestEmptyOutputHandledDeterministically(unittest.TestCase):

    def test_empty_json_object_response_fails_cleanly_not_a_crash(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        provider = MockLLMProvider(fixed_response="{}")

        result = generate_and_record_hypothesis(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertEqual(len(inv.ledger.claims), 0)
        self.assertEqual(len(inv.ledger.hypotheses), 0)

    def test_zero_facts_in_ledger_still_produces_a_deterministic_prompt(self):
        inv = Investigation()  # no documents, no facts at all
        raw = _valid_hypothesis_json("A claim", "An explanation.", [])
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_and_record_hypothesis(inv, provider)

        self.assertTrue(result.success)
        self.assertEqual(inv.ledger.hypotheses[0].referenced_fact_ids, ())


# ---------------------------------------------------------------------
# GROUP H -- Multiple hypotheses / no cross-contamination
# ---------------------------------------------------------------------
class TestMultipleHypothesesNoContamination(unittest.TestCase):

    def test_two_successful_calls_produce_two_distinct_hypotheses(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213"), ("amount", "250.00")])
        raw1 = _valid_hypothesis_json("First claim", "First explanation.", [fact_ids[0]])
        raw2 = _valid_hypothesis_json("Second claim", "Second explanation.", [fact_ids[1]])

        result1 = generate_and_record_hypothesis(inv, MockLLMProvider(fixed_response=raw1))
        result2 = generate_and_record_hypothesis(inv, MockLLMProvider(fixed_response=raw2))

        self.assertTrue(result1.success and result2.success)
        self.assertEqual(len(inv.ledger.hypotheses), 2)
        self.assertNotEqual(result1.hypothesis_id, result2.hypothesis_id)
        self.assertNotEqual(result1.claim_id, result2.claim_id)

    def test_failed_call_after_successful_one_does_not_corrupt_prior_hypothesis(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw_good = _valid_hypothesis_json("A claim", "An explanation.", fact_ids)
        result1 = generate_and_record_hypothesis(inv, MockLLMProvider(fixed_response=raw_good))
        self.assertTrue(result1.success)

        result2 = generate_and_record_hypothesis(inv, MockLLMProvider(fixed_response="not json"))
        self.assertFalse(result2.success)

        # The first hypothesis must still be there, untouched.
        self.assertEqual(len(inv.ledger.hypotheses), 1)
        self.assertEqual(inv.ledger.hypotheses[0].id, result1.hypothesis_id)


# ---------------------------------------------------------------------
# GROUP I -- Hard gates remain unaffected
# ---------------------------------------------------------------------
class TestHardGatesUnaffected(unittest.TestCase):

    def test_case_scope_remains_none(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = _valid_hypothesis_json("A claim", "An explanation.", fact_ids)
        generate_and_record_hypothesis(inv, MockLLMProvider(fixed_response=raw))
        self.assertIsNone(inv.case_scope)

    def test_final_status_remains_none(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = _valid_hypothesis_json("A claim", "An explanation.", fact_ids)
        generate_and_record_hypothesis(inv, MockLLMProvider(fixed_response=raw))
        self.assertIsNone(inv.final_status)

    def test_state_machine_not_advanced(self):
        from billwatch import InvestigationState
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = _valid_hypothesis_json("A claim", "An explanation.", fact_ids)
        generate_and_record_hypothesis(inv, MockLLMProvider(fixed_response=raw))
        self.assertEqual(inv.state, InvestigationState.INGESTED)

    def test_appeal_eligibility_remains_false(self):
        inv, fact_ids = _investigation_with_facts([("code", "99213")])
        raw = _valid_hypothesis_json("A claim", "An explanation.", fact_ids)
        generate_and_record_hypothesis(inv, MockLLMProvider(fixed_response=raw))
        self.assertFalse(inv.can_draft_appeal())

    def test_non_investigation_input_rejected(self):
        provider = MockLLMProvider(fixed_response="{}")
        with self.assertRaises(HypothesisIntegrationError):
            generate_and_record_hypothesis("not an investigation", provider)  # type: ignore[arg-type]

    def test_no_provider_class_imported_into_this_module(self):
        import sys
        this_module = sys.modules[__name__]
        self.assertNotIn("GeminiProvider", vars(this_module))
        self.assertNotIn("GenAISDKProvider", vars(this_module))


if __name__ == "__main__":
    unittest.main()
