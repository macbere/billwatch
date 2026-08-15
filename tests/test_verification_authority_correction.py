"""
Build 4D pre-work: regression tests for Verification.authority_result.

Confirms the additive correction (Closure Audit item MUST-FIX #1)
preserves the real AuthorityResult alongside the existing collapsed
corroboration_result, without changing any prior behavior.
"""

import unittest

from billwatch import (
    Document, ExtractedFact, Investigation,
    CaseScope, CaseScopeValue, ScopeProvenance, ValidationResult,
)
from billwatch.evidence import Claim, Hypothesis, Verification
from billwatch.authority import AuthorityResult
from billwatch.llm_provider import MockLLMProvider
from billwatch.reference_data import ReferenceStore
from billwatch.reference_bootstrap import load_bootstrap_data
from billwatch.verification_integration import verify_hypothesis
import json


def _bootstrapped_store():
    store = ReferenceStore()
    load_bootstrap_data(store)
    return store


def _investigation_with_hypothesis(code_values, scope_value=None):
    inv = Investigation()
    doc = Document(doc_type="bill", raw_text="synthetic test document")
    inv.ledger.add_document(doc)
    fact_ids = []
    for value in code_values:
        fact = ExtractedFact(document_id=doc.id, fact_type="code", value=value)
        inv.ledger.add_fact(fact)
        fact_ids.append(fact.id)

    if scope_value is not None:
        inv.set_case_scope(CaseScope(
            value=scope_value, provenance=ScopeProvenance.USER_SELECTED,
            source_identifier="test", validation_result=ValidationResult.PASS,
        ))

    claim = Claim(statement="A test claim", related_fact_ids=tuple(fact_ids))
    inv.ledger.add_claim(claim)
    hyp = Hypothesis(claim_id=claim.id, explanation_text="Test.", referenced_fact_ids=tuple(fact_ids))
    inv.ledger.add_hypothesis(hyp)
    return inv, hyp


def _valid_verification_json(hypothesis_id, source_types):
    return json.dumps({
        "hypothesis_id": hypothesis_id,
        "proposed_source_types": list(source_types),
        "verification_rationale": "check it",
    })


class TestAuthoritativePreserved(unittest.TestCase):

    def test_medicare_ncci_preserves_authoritative(self):
        inv, hyp = _investigation_with_hypothesis(
            ["45378", "45380"], scope_value=CaseScopeValue.MEDICARE
        )
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CMS_NCCI"])
        result = verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)

        self.assertTrue(result.success)
        self.assertEqual(inv.ledger.verifications[0].authority_result, "authoritative")
        self.assertEqual(inv.ledger.verifications[0].corroboration_result, "corroborated")


class TestCorroboratingPreserved(unittest.TestCase):

    def test_private_ncci_no_adoption_evidence_preserves_corroborating(self):
        inv, hyp = _investigation_with_hypothesis(
            ["45378", "45380"], scope_value=CaseScopeValue.PRIVATE_COMMERCIAL
        )
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CMS_NCCI"])
        result = verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)

        self.assertTrue(result.success)
        self.assertEqual(inv.ledger.verifications[0].authority_result, "corroborating")
        self.assertEqual(inv.ledger.verifications[0].corroboration_result, "corroborated")


class TestAdmissibleCanBePreserved(unittest.TestCase):

    def test_field_accepts_admissible_value_directly(self):
        # Build 4C's current lookup coverage (CMS_NCCI/CODE_DEFINITION) never
        # produces ADMISSIBLE, so this tests the field's capability directly
        # at the dataclass level, honestly -- not a claim that today's
        # pipeline currently produces this value.
        v = Verification(
            hypothesis_id="h1", corroboration_result="corroborated",
            citation_ref="src1", authority_result=AuthorityResult.ADMISSIBLE.value,
        )
        self.assertEqual(v.authority_result, "admissible")


class TestExistingBehaviorUnchanged(unittest.TestCase):

    def test_hcpcs_lookup_still_produces_correct_verification_counts(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CODE_DEFINITION"])
        result = verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.verifications), 1)
        self.assertEqual(inv.ledger.verifications[0].corroboration_result, "corroborated")
        self.assertEqual(inv.ledger.verifications[0].authority_result, "authoritative")

    def test_missing_evidence_path_unaffected_by_the_new_field(self):
        inv, hyp = _investigation_with_hypothesis(["A0425"])
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["PLAN_POLICY"])
        result = verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)

        self.assertTrue(result.success)
        self.assertEqual(len(inv.ledger.verifications), 0)
        self.assertEqual(len(inv.ledger.missing_evidence), 1)


class TestMissingOrLegacyAuthorityResultSafelyHandled(unittest.TestCase):

    def test_verification_constructed_without_authority_result_defaults_none(self):
        v = Verification(
            hypothesis_id="h1", corroboration_result="silent", citation_ref="src1",
        )
        self.assertIsNone(v.authority_result)

    def test_silent_verification_via_unresolved_scope_has_no_authority_result_confusion(self):
        inv, hyp = _investigation_with_hypothesis(["45378", "45380"])  # no scope set
        store = _bootstrapped_store()
        raw = _valid_verification_json(hyp.id, ["CMS_NCCI"])
        result = verify_hypothesis(inv, hyp.id, MockLLMProvider(fixed_response=raw), store)

        self.assertTrue(result.success)
        self.assertEqual(inv.ledger.verifications[0].corroboration_result, "silent")
        # INSUFFICIENT_SCOPE is still a real AuthorityResult -- it's preserved,
        # just not one that indicates corroboration.
        self.assertEqual(inv.ledger.verifications[0].authority_result, "insufficient_scope")


if __name__ == "__main__":
    unittest.main()
