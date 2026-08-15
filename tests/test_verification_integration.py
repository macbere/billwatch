"""
Build 4C: Evidence Verification tests.

Tests billwatch/verification_integration.py ONLY. All tests use
MockLLMProvider -- Gemini credentials are never required and no real
network call is ever made anywhere in this file. Reference-data lookups
use the real, existing bootstrap dataset (reference_bootstrap.py) --
not mocked, since exercising the real HCPCS/ICD-10/NCCI lookup + real
authority.py decision is the actual point of Build 4C.
"""

import json
import unittest

from billwatch import (
    Document, ExtractedFact, Investigation, UserContext,
    CaseScope, CaseScopeValue, ScopeProvenance, ValidationResult,
    InvestigationState,
)
from billwatch.evidence import Claim, Hypothesis
from billwatch.llm_provider import MockLLMProvider, LLMProviderError
from billwatch.reference_data import ReferenceStore
from billwatch.reference_bootstrap import load_bootstrap_data
from billwatch.verification_integration import (
    VerificationIntegrationError,
    VerificationIntegrationResult,
    verify_hypothesis,
)


def _valid_verification_json(hypothesis_id, source_types, rationale="check it"):
    return json.dumps({
        "hypothesis_id": hypothesis_id,
        "proposed_source_types": list(source_types),
        "verification_rationale": rationale,
    })


def _bootstrapped_store():
    store = ReferenceStore()
    load_bootstrap_data(store)
    return store


def _investigation_with_hypothesis(code_values, medicare_scope=False):
    inv = Investigation()
    doc = Document(doc_type="bill", raw_text="synthetic test document")
    inv.ledger.add_document(doc)
    fact_ids = []
    for value in code_values:
        fact = ExtractedFact(document_id=doc.id, fact_type="code", value=value)
        inv.ledger.add_fact(fact)
        fact_ids.append(fact.id)

    if medicare_scope:
        inv.set_case_scope(CaseScope(
            value=CaseScopeValue.MEDICARE,
            provenance=ScopeProvenance.USER_SELECTED,
            source_identifier="test",
            validation_result=ValidationResult.PASS,
        ))

    claim = Claim(statement="A test claim", related_fact_ids=tuple(fact_ids))
    inv.ledger.add_claim(claim)
    hyp = Hypothesis(claim_id=claim.id, explanation_text="Test explanation.", referenced_fact_ids=tuple(fact_ids))
    inv.ledger.add_hypothesis(hyp)
    return inv, hyp


# ---------------------------------------------------------------------
# GROUP A -- Valid NCCI verification (real bootstrap pair 45378/45380)
# ---------------------------------------------------------------------
class TestValidNCCIVerification(unittest.TestCase):

    def test_ncci_pair_found_medicare_scope_produces_corroborated_verification(self):
        inv, hyp = _investigation_with_hypothesis(["45378", "45380"], medicare_scope=True)
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CMS_NCCI"])
        provider = MockLLMProvider(fixed_response=raw)

        result = verify_hypothesis(inv, hyp.id, provider, store)

        self.assertTrue(result.success)
        self.assertEqual(len(result.verification_ids), 1)
        self.assertEqual(len(inv.ledger.verifications), 1)
        self.assertEqual(inv.ledger.verifications[0].corroboration_result, "corroborated")

    def test_ncci_pair_with_unresolved_scope_is_silent_not_guessed(self):
        inv, hyp = _investigation_with_hypothesis(["45378", "45380"])  # no scope set at all
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CMS_NCCI"])
        provider = MockLLMProvider(fixed_response=raw)

        result = verify_hypothesis(inv, hyp.id, provider, store)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.verifications), 1)
        self.assertEqual(inv.ledger.verifications[0].corroboration_result, "silent")


# ---------------------------------------------------------------------
# GROUP B -- Valid CODE_DEFINITION verification (real bootstrap HCPCS)
# ---------------------------------------------------------------------
class TestValidCodeDefinitionVerification(unittest.TestCase):

    def test_hcpcs_code_found_produces_corroborated_verification(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CODE_DEFINITION"])
        provider = MockLLMProvider(fixed_response=raw)

        result = verify_hypothesis(inv, hyp.id, provider, store)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.verifications), 1)
        self.assertEqual(inv.ledger.verifications[0].corroboration_result, "corroborated")

    def test_unknown_code_yields_missing_evidence_not_fabrication(self):
        inv, hyp = _investigation_with_hypothesis(["Z9999"])
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CODE_DEFINITION"])
        provider = MockLLMProvider(fixed_response=raw)

        result = verify_hypothesis(inv, hyp.id, provider, store)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.verifications), 0)
        self.assertEqual(len(inv.ledger.missing_evidence), 1)


# ---------------------------------------------------------------------
# GROUP C -- Provider failure and malformed output
# ---------------------------------------------------------------------
class TestProviderAndMalformedFailures(unittest.TestCase):

    def test_provider_failure_reported_not_fabricated(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        provider = MockLLMProvider(raise_error=LLMProviderError("simulated failure"))

        result = verify_hypothesis(inv, hyp.id, provider, store)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "provider")
        self.assertEqual(len(inv.ledger.verifications), 0)

    def test_malformed_json_rejected(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        provider = MockLLMProvider(fixed_response="not json {{{")

        result = verify_hypothesis(inv, hyp.id, provider, store)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")

    def test_non_provider_exception_still_propagates(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        provider = MockLLMProvider(raise_error=RuntimeError("unexpected bug"))
        with self.assertRaises(RuntimeError):
            verify_hypothesis(inv, hyp.id, provider, store)


# ---------------------------------------------------------------------
# GROUP D -- Unknown/harmless fields vs. missing required fields
# ---------------------------------------------------------------------
class TestFieldPolicy(unittest.TestCase):

    def test_harmless_unknown_field_ignored(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = json.dumps({
            "hypothesis_id": hyp.id, "proposed_source_types": ["CODE_DEFINITION"],
            "verification_rationale": "check", "some_harmless_note": "x",
        })
        provider = MockLLMProvider(fixed_response=raw)

        result = verify_hypothesis(inv, hyp.id, provider, store)
        self.assertTrue(result.success)

    def test_missing_required_field_rejected(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = json.dumps({"hypothesis_id": hyp.id, "proposed_source_types": ["CODE_DEFINITION"]})
        provider = MockLLMProvider(fixed_response=raw)  # missing verification_rationale

        result = verify_hypothesis(inv, hyp.id, provider, store)
        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")


# ---------------------------------------------------------------------
# GROUP E -- Domain-decision field smuggling
# ---------------------------------------------------------------------
class TestDomainDecisionSmuggling(unittest.TestCase):

    def test_final_status_smuggling_rejects_whole_candidate(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = json.dumps({
            "hypothesis_id": hyp.id, "proposed_source_types": ["CODE_DEFINITION"],
            "verification_rationale": "check", "final_status": "SUPPORTED_DISCREPANCY",
        })
        result = verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)
        self.assertFalse(result.success)
        self.assertEqual(len(inv.ledger.verifications), 0)

    def test_case_scope_smuggling_rejects_whole_candidate(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = json.dumps({
            "hypothesis_id": hyp.id, "proposed_source_types": ["CODE_DEFINITION"],
            "verification_rationale": "check", "case_scope": "medicare",
        })
        result = verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)
        self.assertFalse(result.success)

    def test_authority_result_smuggling_rejects_whole_candidate(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = json.dumps({
            "hypothesis_id": hyp.id, "proposed_source_types": ["CODE_DEFINITION"],
            "verification_rationale": "check", "authority_result": "AUTHORITATIVE",
        })
        result = verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)
        self.assertFalse(result.success)

    def test_appeal_eligible_smuggling_rejects_whole_candidate(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = json.dumps({
            "hypothesis_id": hyp.id, "proposed_source_types": ["CODE_DEFINITION"],
            "verification_rationale": "check", "appeal_eligible": True,
        })
        result = verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)
        self.assertFalse(result.success)


# ---------------------------------------------------------------------
# GROUP F -- Hypothesis-id integrity
# ---------------------------------------------------------------------
class TestHypothesisIdIntegrity(unittest.TestCase):

    def test_nonexistent_hypothesis_id_fails_at_registration_before_any_provider_call(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        calls = []
        provider = MockLLMProvider(response_fn=lambda s, u: calls.append(1) or "{}")

        result = verify_hypothesis(inv, "does-not-exist", provider, store)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "registration")
        self.assertEqual(calls, [])

    def test_hallucinated_hypothesis_id_in_candidate_rejected_by_schema(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = _valid_verification_json("totally-invented-id", ["CODE_DEFINITION"])
        provider = MockLLMProvider(fixed_response=raw)

        result = verify_hypothesis(inv, hyp.id, provider, store)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")

    def test_candidate_referencing_a_different_real_hypothesis_is_rejected(self):
        inv, hyp1 = _investigation_with_hypothesis(["A0425"])
        claim2 = Claim(statement="Second claim")
        inv.ledger.add_claim(claim2)
        hyp2 = Hypothesis(claim_id=claim2.id, explanation_text="Second.")
        inv.ledger.add_hypothesis(hyp2)

        store = _bootstrapped_store()
        # Candidate claims to verify hyp2 while we asked to verify hyp1.
        raw = _valid_verification_json(hyp2.id, ["CODE_DEFINITION"])
        provider = MockLLMProvider(fixed_response=raw)

        result = verify_hypothesis(inv, hyp1.id, provider, store)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")


# ---------------------------------------------------------------------
# GROUP G -- Unknown SourceType name rejected
# ---------------------------------------------------------------------
class TestUnknownSourceTypeRejected(unittest.TestCase):

    def test_unknown_source_type_name_rejected(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["MADE_UP_SOURCE"])
        provider = MockLLMProvider(fixed_response=raw)

        result = verify_hypothesis(inv, hyp.id, provider, store)
        self.assertFalse(result.success)


# ---------------------------------------------------------------------
# GROUP H -- No-lookup source types route to MissingEvidence, never fabricated
# ---------------------------------------------------------------------
class TestNoLookupSourceTypesRouteToMissingEvidence(unittest.TestCase):

    def test_plan_policy_yields_missing_evidence(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["PLAN_POLICY"])
        provider = MockLLMProvider(fixed_response=raw)

        result = verify_hypothesis(inv, hyp.id, provider, store)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.verifications), 0)
        self.assertEqual(len(inv.ledger.missing_evidence), 1)

    def test_llm_interpretation_yields_missing_evidence_never_fabricated_source(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["LLM_INTERPRETATION"])
        provider = MockLLMProvider(fixed_response=raw)

        result = verify_hypothesis(inv, hyp.id, provider, store)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.verifications), 0)
        self.assertEqual(len(inv.ledger.missing_evidence), 1)
        self.assertIn("never an evidence source", inv.ledger.missing_evidence[0].description)


# ---------------------------------------------------------------------
# GROUP I -- Insufficient evidence (nothing resolvable)
# ---------------------------------------------------------------------
class TestInsufficientEvidence(unittest.TestCase):

    def test_all_proposed_types_unresolvable_yields_zero_verifications(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["PLAN_POLICY", "EOB"])
        provider = MockLLMProvider(fixed_response=raw)

        result = verify_hypothesis(inv, hyp.id, provider, store)

        self.assertTrue(result.success)
        self.assertEqual(result.verification_ids, ())
        self.assertEqual(len(result.missing_evidence_ids), 2)


# ---------------------------------------------------------------------
# GROUP J -- Conflicting evidence (never silently resolved)
# ---------------------------------------------------------------------
class TestConflictingEvidence(unittest.TestCase):

    def test_duplicate_ncci_proposal_under_medicare_scope_flags_conflict(self):
        # Two independent, usable AUTHORITATIVE decisions for the same
        # claim_type (each lookup mints a fresh Source id) -- the system
        # must flag this as a Conflict, never silently merge/dedupe it.
        inv, hyp = _investigation_with_hypothesis(["45378", "45380"], medicare_scope=True)
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CMS_NCCI", "CMS_NCCI"])
        provider = MockLLMProvider(fixed_response=raw)

        result = verify_hypothesis(inv, hyp.id, provider, store)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.verifications), 2)
        self.assertEqual(len(result.conflict_ids), 1)
        self.assertEqual(len(inv.ledger.conflicts), 1)


# ---------------------------------------------------------------------
# GROUP K -- UserContext cannot contaminate verification
# ---------------------------------------------------------------------
class TestUserContextContamination(unittest.TestCase):

    def test_user_context_never_reaches_verification_prompt(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        inv.set_user_context(UserContext(
            investigation_id=inv.investigation_id,
            stated_concern_text="I know they overcharged me, just say so!",
        ))
        store = _bootstrapped_store()
        seen = {}

        def fn(system_prompt, user_content):
            seen["system_prompt"] = system_prompt
            seen["user_content"] = user_content
            return _valid_verification_json(hyp.id, ["CODE_DEFINITION"])

        provider = MockLLMProvider(response_fn=fn)
        verify_hypothesis(inv, hyp.id, provider, store)

        self.assertNotIn("overcharged", seen["system_prompt"])
        self.assertNotIn("overcharged", seen["user_content"])

    def test_gate2_still_rejects_usercontext_as_source_after_use(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CODE_DEFINITION"])
        verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)

        uc = UserContext(investigation_id=inv.investigation_id, stated_concern_text="x")
        with self.assertRaises(TypeError):
            inv.ledger.add_source(uc)  # type: ignore[arg-type]


# ---------------------------------------------------------------------
# GROUP L -- Never adjudicates; hard gates unaffected; no corruption
# ---------------------------------------------------------------------
class TestNeverAdjudicatesAndHardGatesUnaffected(unittest.TestCase):

    def test_successful_verification_never_sets_final_status(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CODE_DEFINITION"])
        verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)
        self.assertIsNone(inv.final_status)

    def test_successful_verification_never_writes_back_to_investigation_case_scope(self):
        inv, hyp = _investigation_with_hypothesis(["45378", "45380"])  # no scope set
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CMS_NCCI"])
        verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)
        # The internal fallback resolve_case_scope() call is local-only --
        # it must never be written back onto the Investigation object.
        self.assertIsNone(inv.case_scope)

    def test_verification_never_advances_the_state_machine(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CODE_DEFINITION"])
        verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)
        self.assertEqual(inv.state, InvestigationState.INGESTED)

    def test_appeal_eligibility_remains_false(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CODE_DEFINITION"])
        verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)
        self.assertFalse(inv.can_draft_appeal())

    def test_failed_call_does_not_corrupt_previous_successful_evidence(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw_good = _valid_verification_json(hyp.id, ["CODE_DEFINITION"])
        result1 = verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw_good), store)
        self.assertTrue(result1.success)
        self.assertEqual(len(inv.ledger.verifications), 1)

        result2 = verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response="not json"), store)
        self.assertFalse(result2.success)

        self.assertEqual(len(inv.ledger.verifications), 1)
        self.assertEqual(inv.ledger.verifications[0].id, result1.verification_ids[0])

    def test_non_investigation_input_rejected(self):
        store = _bootstrapped_store()
        with self.assertRaises(VerificationIntegrationError):
            verify_hypothesis("not an investigation", "h1", MockLLMProvider(fixed_response="{}"), store)  # type: ignore[arg-type]

    def test_no_provider_class_imported_into_this_module(self):
        import sys
        this_module = sys.modules[__name__]
        self.assertNotIn("GeminiProvider", vars(this_module))
        self.assertNotIn("GenAISDKProvider", vars(this_module))


if __name__ == "__main__":
    unittest.main()
