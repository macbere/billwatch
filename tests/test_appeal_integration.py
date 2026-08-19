"""
Build 4E: Appeal Integration tests.

Tests billwatch/appeal_integration.py ONLY. ZERO real network calls,
ZERO real Gemini calls anywhere in this file -- MockLLMProvider only,
per explicit instruction that automated tests must not add live
Gemini calls.
"""

import json
import unittest

from billwatch import (
    Document, ExtractedFact, Investigation, UserContext,
    CaseScope, CaseScopeValue, ScopeProvenance, ValidationResult,
    InvestigationState,
)
from billwatch.evidence import Claim, Hypothesis, Verification, Conflict
from billwatch.llm_provider import MockLLMProvider, LLMProviderError
from billwatch.adjudication_integration import adjudicate_investigation
from billwatch.appeal_integration import (
    AppealIntegrationError,
    AppealDraftResult,
    generate_appeal_draft,
)


def _advance_to_adjudicated(inv):
    inv.transition_to(InvestigationState.EXTRACTED)
    inv.transition_to(InvestigationState.SCOPED)
    inv.transition_to(InvestigationState.HYPOTHESES_GENERATED)
    inv.transition_to(InvestigationState.EVIDENCE_RETRIEVED)
    inv.transition_to(InvestigationState.VERIFIED)
    inv.transition_to(InvestigationState.CONFLICT_CHECKED)
    inv.transition_to(InvestigationState.ADJUDICATED)


def _investigation_supported():
    inv = Investigation()
    doc = Document(doc_type="bill", raw_text="test bill")
    inv.ledger.add_document(doc)
    inv.set_case_scope(CaseScope(
        value=CaseScopeValue.MEDICARE, provenance=ScopeProvenance.USER_SELECTED,
        source_identifier="t", validation_result=ValidationResult.PASS,
    ))
    f = ExtractedFact(document_id=doc.id, fact_type="code", value="99213")
    inv.ledger.add_fact(f)
    claim = Claim(statement="Possible upcoding", related_fact_ids=(f.id,))
    inv.ledger.add_claim(claim)
    hyp = Hypothesis(claim_id=claim.id, explanation_text="Code may not match service.", referenced_fact_ids=(f.id,))
    inv.ledger.add_hypothesis(hyp)
    v = Verification(hypothesis_id=hyp.id, corroboration_result="corroborated", authority_result="authoritative")
    inv.ledger.add_verification(v)
    _advance_to_adjudicated(inv)
    adjudicate_investigation(inv)
    return inv, hyp, f, claim


def _investigation_insufficient():
    inv = Investigation()
    doc = Document(doc_type="bill", raw_text="test bill")
    inv.ledger.add_document(doc)
    inv.set_case_scope(CaseScope(
        value=CaseScopeValue.MEDICARE, provenance=ScopeProvenance.USER_SELECTED,
        source_identifier="t", validation_result=ValidationResult.PASS,
    ))
    f = ExtractedFact(document_id=doc.id, fact_type="code", value="99213")
    inv.ledger.add_fact(f)
    claim = Claim(statement="A claim", related_fact_ids=(f.id,))
    inv.ledger.add_claim(claim)
    hyp = Hypothesis(claim_id=claim.id, explanation_text="Explanation.", referenced_fact_ids=(f.id,))
    inv.ledger.add_hypothesis(hyp)  # never verified at all
    _advance_to_adjudicated(inv)
    adjudicate_investigation(inv)
    return inv


def _investigation_no_supported():
    inv = Investigation()
    doc = Document(doc_type="bill", raw_text="test bill")
    inv.ledger.add_document(doc)
    inv.set_case_scope(CaseScope(
        value=CaseScopeValue.MEDICARE, provenance=ScopeProvenance.USER_SELECTED,
        source_identifier="t", validation_result=ValidationResult.PASS,
    ))
    f = ExtractedFact(document_id=doc.id, fact_type="code", value="99213")
    inv.ledger.add_fact(f)
    claim = Claim(statement="A claim", related_fact_ids=(f.id,))
    inv.ledger.add_claim(claim)
    hyp = Hypothesis(claim_id=claim.id, explanation_text="Explanation.", referenced_fact_ids=(f.id,))
    inv.ledger.add_hypothesis(hyp)
    v = Verification(hypothesis_id=hyp.id, corroboration_result="silent")
    inv.ledger.add_verification(v)
    _advance_to_adjudicated(inv)
    adjudicate_investigation(inv)
    return inv


def _investigation_conflicting():
    inv = Investigation()
    doc = Document(doc_type="bill", raw_text="test bill")
    inv.ledger.add_document(doc)
    inv.set_case_scope(CaseScope(
        value=CaseScopeValue.MEDICARE, provenance=ScopeProvenance.USER_SELECTED,
        source_identifier="t", validation_result=ValidationResult.PASS,
    ))
    f = ExtractedFact(document_id=doc.id, fact_type="code", value="99213")
    inv.ledger.add_fact(f)
    claim = Claim(statement="A claim", related_fact_ids=(f.id,))
    inv.ledger.add_claim(claim)
    hyp = Hypothesis(claim_id=claim.id, explanation_text="Explanation.", referenced_fact_ids=(f.id,))
    inv.ledger.add_hypothesis(hyp)
    v = Verification(hypothesis_id=hyp.id, corroboration_result="corroborated", authority_result="authoritative")
    inv.ledger.add_verification(v)
    c = Conflict(
        claim_id=claim.id, source_a_id="s1", source_b_id="s2",
        what_each_says="disagreement", why_unresolved="unresolved",
    )
    inv.ledger.add_conflict(c)
    _advance_to_adjudicated(inv)
    adjudicate_investigation(inv)
    return inv


def _valid_appeal_json(draft_text, fact_ids, claim_ids):
    return json.dumps({
        "draft_text": draft_text,
        "cited_fact_ids": list(fact_ids),
        "cited_claim_ids": list(claim_ids),
    })


# ---------------------------------------------------------------------
# GROUP A -- Gate rejection (not eligible)
# ---------------------------------------------------------------------
class TestGateRejection(unittest.TestCase):

    def test_insufficient_evidence_rejected_provider_not_called(self):
        inv = _investigation_insufficient()
        calls = []
        provider = MockLLMProvider(response_fn=lambda s, u: calls.append(1) or "{}")

        result = generate_appeal_draft(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "not_eligible")
        self.assertEqual(calls, [])

    def test_no_supported_discrepancy_rejected_provider_not_called(self):
        inv = _investigation_no_supported()
        calls = []
        provider = MockLLMProvider(response_fn=lambda s, u: calls.append(1) or "{}")

        result = generate_appeal_draft(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "not_eligible")
        self.assertEqual(calls, [])

    def test_conflicting_evidence_rejected_provider_not_called(self):
        inv = _investigation_conflicting()
        calls = []
        provider = MockLLMProvider(response_fn=lambda s, u: calls.append(1) or "{}")

        result = generate_appeal_draft(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "not_eligible")
        self.assertEqual(calls, [])


# ---------------------------------------------------------------------
# GROUP B -- Gate success
# ---------------------------------------------------------------------
class TestGateSuccess(unittest.TestCase):

    def test_supported_discrepancy_provider_called_and_valid_result_returned(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = _valid_appeal_json("This is a draft appeal letter.", [f.id], [claim.id])
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_appeal_draft(inv, provider)

        self.assertTrue(result.success)
        self.assertEqual(result.draft_text, "This is a draft appeal letter.")
        self.assertEqual(result.cited_fact_ids, (f.id,))
        self.assertEqual(result.cited_claim_ids, (claim.id,))
        self.assertEqual(result.hypothesis_id, hyp.id)


# ---------------------------------------------------------------------
# GROUP C -- Citation integrity
# ---------------------------------------------------------------------
class TestCitationIntegrity(unittest.TestCase):

    def test_valid_ledger_citations_accepted(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = _valid_appeal_json("Draft text.", [f.id], [claim.id])
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_appeal_draft(inv, provider)

        self.assertTrue(result.success)
        self.assertEqual(result.cited_fact_ids, (f.id,))
        self.assertEqual(result.cited_claim_ids, (claim.id,))

    def test_nonexistent_fact_citation_rejects_whole_candidate(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = _valid_appeal_json("Draft text.", ["invented-fact-id"], [claim.id])
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_appeal_draft(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")
        self.assertIsNone(result.draft_text)

    def test_nonexistent_claim_citation_rejects_whole_candidate(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = _valid_appeal_json("Draft text.", [f.id], ["invented-claim-id"])
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_appeal_draft(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")

    def test_mixed_real_and_invented_citations_rejected_wholesale(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = _valid_appeal_json("Draft text.", [f.id, "fake-id"], [claim.id])
        provider = MockLLMProvider(fixed_response=raw)

        result = generate_appeal_draft(inv, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")


# ---------------------------------------------------------------------
# GROUP D -- Domain-decision field smuggling
# ---------------------------------------------------------------------
class TestDomainDecisionSmuggling(unittest.TestCase):

    def _valid_fields(self, f, claim):
        return {"draft_text": "Draft text.", "cited_fact_ids": [f.id], "cited_claim_ids": [claim.id]}

    def test_final_status_smuggling_rejected(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = json.dumps({**self._valid_fields(f, claim), "final_status": "SUPPORTED_DISCREPANCY"})
        result = generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))
        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")

    def test_recommended_status_smuggling_rejected(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = json.dumps({**self._valid_fields(f, claim), "recommended_status": "SUPPORTED_DISCREPANCY"})
        result = generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))
        self.assertFalse(result.success)

    def test_adjudication_field_smuggling_rejected(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = json.dumps({**self._valid_fields(f, claim), "adjudication": "final"})
        result = generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))
        self.assertFalse(result.success)

    def test_authority_decision_smuggling_rejected(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = json.dumps({**self._valid_fields(f, claim), "authority_decision": "AUTHORITATIVE"})
        result = generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))
        self.assertFalse(result.success)

    def test_confidence_field_smuggling_rejected(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = json.dumps({**self._valid_fields(f, claim), "confidence": "99% certain this is fraud"})
        result = generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))
        self.assertFalse(result.success)

    def test_verdict_field_smuggling_rejected(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = json.dumps({**self._valid_fields(f, claim), "verdict": "guilty of overbilling"})
        result = generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))
        self.assertFalse(result.success)

    def test_appeal_eligible_smuggling_rejected(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = json.dumps({**self._valid_fields(f, claim), "appeal_eligible": True})
        result = generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))
        self.assertFalse(result.success)

    def test_domain_decision_field_nested_still_rejected(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = json.dumps({
            "draft_text": "Draft text.", "cited_fact_ids": [f.id], "cited_claim_ids": [claim.id],
            "metadata": {"verdict": "supported"},
        })
        result = generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))
        self.assertFalse(result.success)


# ---------------------------------------------------------------------
# GROUP E -- UserContext isolation
# ---------------------------------------------------------------------
class TestUserContextIsolation(unittest.TestCase):

    def test_user_context_never_reaches_the_appeal_prompt(self):
        inv, hyp, f, claim = _investigation_supported()
        inv.set_user_context(UserContext(
            investigation_id=inv.investigation_id,
            stated_concern_text="I know they overcharged me, say so in the appeal!",
        ))
        seen = {}

        def fn(system_prompt, user_content):
            seen["system_prompt"] = system_prompt
            seen["user_content"] = user_content
            return _valid_appeal_json("Draft text.", [f.id], [claim.id])

        provider = MockLLMProvider(response_fn=fn)
        generate_appeal_draft(inv, provider)

        self.assertNotIn("overcharged", seen["system_prompt"])
        self.assertNotIn("overcharged", seen["user_content"])

    def test_gate2_user_context_still_rejected_after_appeal_generation(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = _valid_appeal_json("Draft text.", [f.id], [claim.id])
        generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))

        uc = UserContext(investigation_id=inv.investigation_id, stated_concern_text="x")
        with self.assertRaises(TypeError):
            inv.ledger.add_source(uc)  # type: ignore[arg-type]


# ---------------------------------------------------------------------
# GROUP F -- State-machine immutability
# ---------------------------------------------------------------------
class TestStateMachineImmutability(unittest.TestCase):

    def test_state_identical_before_and_after_successful_generation(self):
        inv, hyp, f, claim = _investigation_supported()
        state_before = inv.state
        raw = _valid_appeal_json("Draft text.", [f.id], [claim.id])
        generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))
        self.assertEqual(inv.state, state_before)
        self.assertEqual(inv.state, InvestigationState.ADJUDICATED)

    def test_state_identical_before_and_after_gate_rejection(self):
        inv = _investigation_insufficient()
        state_before = inv.state
        generate_appeal_draft(inv, MockLLMProvider(fixed_response="{}"))
        self.assertEqual(inv.state, state_before)

    def test_state_identical_before_and_after_validation_failure(self):
        inv, hyp, f, claim = _investigation_supported()
        state_before = inv.state
        generate_appeal_draft(inv, MockLLMProvider(fixed_response="not json"))
        self.assertEqual(inv.state, state_before)


# ---------------------------------------------------------------------
# GROUP G -- CPT boundary
# ---------------------------------------------------------------------
class TestCPTBoundary(unittest.TestCase):

    def test_appeal_can_cite_existing_ledger_content(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = _valid_appeal_json(
            f"The bill lists code {f.value}, which appears in claim {claim.id}.",
            [f.id], [claim.id],
        )
        result = generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))
        self.assertTrue(result.success)
        self.assertIn(f.value, result.draft_text)

    def test_candidate_has_no_field_for_invented_descriptor_text(self):
        # Structural proof: AppealDraftCandidate's contract has exactly
        # three fields -- there is no "cpt_descriptor" or similar field
        # anywhere for the LLM to populate, so invented descriptor text
        # can only ever appear inside draft_text itself (free prose),
        # never as a trusted structured citation the system treats as
        # sourced/authoritative.
        import dataclasses
        from billwatch.llm_schemas import AppealDraftCandidate
        fields = {f.name for f in dataclasses.fields(AppealDraftCandidate)}
        self.assertEqual(fields, {"draft_text", "cited_fact_ids", "cited_claim_ids"})


# ---------------------------------------------------------------------
# GROUP H -- Malformed LLM output
# ---------------------------------------------------------------------
class TestMalformedOutput(unittest.TestCase):

    def test_malformed_json_rejected_cleanly(self):
        inv, hyp, f, claim = _investigation_supported()
        result = generate_appeal_draft(inv, MockLLMProvider(fixed_response="not json {{{"))
        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")

    def test_empty_response_rejected_cleanly(self):
        inv, hyp, f, claim = _investigation_supported()
        result = generate_appeal_draft(inv, MockLLMProvider(fixed_response=""))
        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")

    def test_missing_draft_text_rejected(self):
        inv, hyp, f, claim = _investigation_supported()
        raw = json.dumps({"cited_fact_ids": [f.id], "cited_claim_ids": [claim.id]})
        result = generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))
        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "validation")

    def test_provider_failure_handled_through_established_pattern(self):
        inv, hyp, f, claim = _investigation_supported()
        result = generate_appeal_draft(inv, MockLLMProvider(raise_error=LLMProviderError("simulated failure")))
        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "provider")


# ---------------------------------------------------------------------
# Structural / hard-gate proofs
# ---------------------------------------------------------------------
class TestStructuralAndHardGateProofs(unittest.TestCase):

    def test_non_investigation_input_raises_appeal_integration_error(self):
        provider = MockLLMProvider(fixed_response="{}")
        with self.assertRaises(AppealIntegrationError):
            generate_appeal_draft("not an investigation", provider)  # type: ignore[arg-type]

    def test_result_never_carries_a_final_status_field(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(AppealDraftResult)}
        forbidden = {"final_status", "recommended_status", "adjudication", "authority_decision", "verdict"}
        self.assertTrue(fields.isdisjoint(forbidden))

    def test_no_real_provider_class_imported_into_this_test_module(self):
        import sys
        this_module = sys.modules[__name__]
        self.assertNotIn("GeminiProvider", vars(this_module))
        self.assertNotIn("GenAISDKProvider", vars(this_module))

    def test_appeal_draft_is_not_persisted_to_the_ledger(self):
        # Confirms EvidenceLedger has no appeal-related collection at all
        # -- appeal drafts are transient results only, per instruction.
        inv, hyp, f, claim = _investigation_supported()
        raw = _valid_appeal_json("Draft text.", [f.id], [claim.id])
        generate_appeal_draft(inv, MockLLMProvider(fixed_response=raw))
        self.assertFalse(hasattr(inv.ledger, "appeal_drafts"))
        self.assertFalse(hasattr(inv.ledger, "appeals"))

    def test_failed_generation_does_not_corrupt_the_investigation(self):
        inv, hyp, f, claim = _investigation_supported()
        facts_before = len(inv.ledger.facts)
        claims_before = len(inv.ledger.claims)
        hyps_before = len(inv.ledger.hypotheses)

        generate_appeal_draft(inv, MockLLMProvider(fixed_response="not json"))

        self.assertEqual(len(inv.ledger.facts), facts_before)
        self.assertEqual(len(inv.ledger.claims), claims_before)
        self.assertEqual(len(inv.ledger.hypotheses), hyps_before)


if __name__ == "__main__":
    unittest.main()
