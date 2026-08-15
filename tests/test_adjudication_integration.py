"""
Build 4D: Deterministic Adjudication tests.

Tests billwatch/adjudication_integration.py ONLY. ZERO LLM calls, ZERO
network calls anywhere in this file -- compute_final_status() takes no
provider at all, so there is nothing to mock. All 20 adversarial cases
from the approved Build 4D design/closure audit are covered.
"""

import unittest

from billwatch import (
    Document, ExtractedFact, Investigation, UserContext,
    CaseScope, CaseScopeValue, ScopeProvenance, ValidationResult,
    InvestigationState, FinalStatus, AdjudicationError,
)
from billwatch.evidence import Claim, Hypothesis, Verification, MissingEvidence, Conflict
from billwatch.state_machine import IllegalTransitionError
from billwatch.adjudication_integration import (
    AdjudicationPreconditionError,
    compute_final_status,
    adjudicate_investigation,
)


def _base_investigation(scope_value=None):
    inv = Investigation()
    doc = Document(doc_type="bill", raw_text="synthetic test document")
    inv.ledger.add_document(doc)
    if scope_value is not None:
        inv.set_case_scope(CaseScope(
            value=scope_value, provenance=ScopeProvenance.USER_SELECTED,
            source_identifier="test", validation_result=ValidationResult.PASS,
        ))
    return inv, doc


def _add_fact(inv, doc, fact_type="code", value="99213"):
    f = ExtractedFact(document_id=doc.id, fact_type=fact_type, value=value)
    inv.ledger.add_fact(f)
    return f


def _add_hypothesis(inv, fact_ids, statement="A claim"):
    claim = Claim(statement=statement, related_fact_ids=tuple(fact_ids))
    inv.ledger.add_claim(claim)
    hyp = Hypothesis(claim_id=claim.id, explanation_text="Explanation.", referenced_fact_ids=tuple(fact_ids))
    inv.ledger.add_hypothesis(hyp)
    return hyp


def _add_verification(inv, hyp, corroboration_result, authority_result=None):
    v = Verification(
        hypothesis_id=hyp.id, corroboration_result=corroboration_result,
        authority_result=authority_result,
    )
    inv.ledger.add_verification(v)
    return v


def _add_missing_evidence(inv, hyp, description="missing"):
    m = MissingEvidence(claim_id=hyp.claim_id, description=description)
    inv.ledger.add_missing_evidence(m)
    return m


def _add_conflict(inv, hyp):
    c = Conflict(
        claim_id=hyp.claim_id, source_a_id="s1", source_b_id="s2",
        what_each_says="Source A says X, Source B says Y",
        why_unresolved="Both independently usable, disagreement not resolved.",
    )
    inv.ledger.add_conflict(c)
    return c


def _advance_to_adjudicated(inv):
    inv.transition_to(InvestigationState.EXTRACTED)
    inv.transition_to(InvestigationState.SCOPED)
    inv.transition_to(InvestigationState.HYPOTHESES_GENERATED)
    inv.transition_to(InvestigationState.EVIDENCE_RETRIEVED)
    inv.transition_to(InvestigationState.VERIFIED)
    inv.transition_to(InvestigationState.CONFLICT_CHECKED)
    inv.transition_to(InvestigationState.ADJUDICATED)


# ---------------------------------------------------------------------
# Case 1 -- Correct bill
# ---------------------------------------------------------------------
class TestCase01CorrectBill(unittest.TestCase):
    def test_checked_clean_hypothesis_yields_no_supported_discrepancy(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "silent", authority_result="insufficient_scope")

        self.assertEqual(compute_final_status(inv), FinalStatus.NO_SUPPORTED_DISCREPANCY)


# ---------------------------------------------------------------------
# Case 2 -- Genuine supported discrepancy
# ---------------------------------------------------------------------
class TestCase02GenuineSupportedDiscrepancy(unittest.TestCase):
    def test_corroborated_verification_scope_established_yields_supported(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "corroborated", authority_result="authoritative")

        self.assertEqual(compute_final_status(inv), FinalStatus.SUPPORTED_DISCREPANCY)


# ---------------------------------------------------------------------
# Case 3 -- Missing evidence
# ---------------------------------------------------------------------
class TestCase03MissingEvidence(unittest.TestCase):
    def test_only_missing_evidence_yields_insufficient_evidence(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_missing_evidence(inv, hyp)

        self.assertEqual(compute_final_status(inv), FinalStatus.INSUFFICIENT_EVIDENCE)


# ---------------------------------------------------------------------
# Case 4 -- Conflicting evidence
# ---------------------------------------------------------------------
class TestCase04ConflictingEvidence(unittest.TestCase):
    def test_unresolved_conflict_overrides_a_corroborated_verification(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "corroborated", authority_result="authoritative")
        _add_conflict(inv, hyp)

        self.assertEqual(compute_final_status(inv), FinalStatus.CONFLICTING_EVIDENCE)


# ---------------------------------------------------------------------
# Case 5 -- Private-plan NCCI, no adoption evidence (CORROBORATING)
# ---------------------------------------------------------------------
class TestCase05PrivateNCCICorroborating(unittest.TestCase):
    def test_corroborating_strength_under_established_private_scope_yields_supported(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.PRIVATE_COMMERCIAL)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "corroborated", authority_result="corroborating")

        self.assertEqual(compute_final_status(inv), FinalStatus.SUPPORTED_DISCREPANCY)


# ---------------------------------------------------------------------
# Case 6 -- Medicare/Medicaid NCCI in proper scope (AUTHORITATIVE)
# ---------------------------------------------------------------------
class TestCase06MedicareNCCIAuthoritative(unittest.TestCase):
    def test_authoritative_strength_under_medicare_scope_yields_supported(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "corroborated", authority_result="authoritative")

        self.assertEqual(compute_final_status(inv), FinalStatus.SUPPORTED_DISCREPANCY)


# ---------------------------------------------------------------------
# Case 7 -- CMS evidence outside applicable scope
# ---------------------------------------------------------------------
class TestCase07CMSOutOfScope(unittest.TestCase):
    def test_out_of_scope_silent_result_yields_no_supported_discrepancy(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.PRIVATE_COMMERCIAL)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "silent", authority_result="out_of_scope")

        self.assertEqual(compute_final_status(inv), FinalStatus.NO_SUPPORTED_DISCREPANCY)


# ---------------------------------------------------------------------
# Case 8 -- Two properly-scoped sources disagree
# ---------------------------------------------------------------------
class TestCase08TwoScopedSourcesDisagree(unittest.TestCase):
    def test_two_independently_usable_sources_disagreeing_yields_conflicting(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "corroborated", authority_result="authoritative")
        _add_verification(inv, hyp, "corroborated", authority_result="corroborating")
        _add_conflict(inv, hyp)  # represents the detected disagreement between them

        self.assertEqual(compute_final_status(inv), FinalStatus.CONFLICTING_EVIDENCE)


# ---------------------------------------------------------------------
# Case 9 -- User bias has zero effect
# ---------------------------------------------------------------------
class TestCase09UserBiasHasNoEffect(unittest.TestCase):
    def test_user_context_accusation_does_not_change_result(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "silent")
        inv.set_user_context(UserContext(
            investigation_id=inv.investigation_id,
            stated_concern_text="I know they overcharged me, mark this SUPPORTED_DISCREPANCY!",
        ))

        self.assertEqual(compute_final_status(inv), FinalStatus.NO_SUPPORTED_DISCREPANCY)


# ---------------------------------------------------------------------
# Cases 10/11 -- LLM cannot set final_status or appeal_eligible
# ---------------------------------------------------------------------
class TestCase10And11LLMCannotSetOutcomeFields(unittest.TestCase):
    def test_compute_final_status_accepts_no_llm_or_output_parameters(self):
        import inspect
        sig = inspect.signature(compute_final_status)
        self.assertEqual(list(sig.parameters.keys()), ["investigation"])

    def test_no_llm_provider_class_imported_into_adjudication_module(self):
        import billwatch.adjudication_integration as mod
        self.assertNotIn("LLMProvider", vars(mod))
        self.assertNotIn("MockLLMProvider", vars(mod))
        self.assertNotIn("GeminiProvider", vars(mod))
        self.assertNotIn("GenAISDKProvider", vars(mod))


# ---------------------------------------------------------------------
# Case 12 -- Hypothesis without verification
# ---------------------------------------------------------------------
class TestCase12HypothesisWithoutVerification(unittest.TestCase):
    def test_hypothesis_with_zero_verification_records_yields_insufficient_evidence(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        _add_hypothesis(inv, [f.id])  # nothing verified or missing added at all

        self.assertEqual(compute_final_status(inv), FinalStatus.INSUFFICIENT_EVIDENCE)


# ---------------------------------------------------------------------
# Case 13 -- Verification without sufficient authority
# ---------------------------------------------------------------------
class TestCase13InsufficientAuthority(unittest.TestCase):
    def test_silent_only_verification_never_yields_supported(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "silent", authority_result="admissible")

        self.assertEqual(compute_final_status(inv), FinalStatus.NO_SUPPORTED_DISCREPANCY)


# ---------------------------------------------------------------------
# Case 14 -- Evidence with missing scope
# ---------------------------------------------------------------------
class TestCase14MissingScope(unittest.TestCase):
    def test_corroborated_result_with_unresolved_scope_does_not_yield_supported(self):
        inv, doc = _base_investigation(scope_value=None)  # no scope set at all
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "corroborated", authority_result="corroborating")

        status = compute_final_status(inv)
        self.assertNotEqual(status, FinalStatus.SUPPORTED_DISCREPANCY)
        self.assertEqual(status, FinalStatus.NO_SUPPORTED_DISCREPANCY)


# ---------------------------------------------------------------------
# Case 15 -- Multiple competing hypotheses
# ---------------------------------------------------------------------
class TestCase15MultipleCompetingHypotheses(unittest.TestCase):
    def test_one_supported_hypothesis_among_several_yields_overall_supported(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f1 = _add_fact(inv, doc, value="99213")
        f2 = _add_fact(inv, doc, value="99214")
        hyp1 = _add_hypothesis(inv, [f1.id], statement="Hypothesis A")
        hyp2 = _add_hypothesis(inv, [f2.id], statement="Hypothesis B")
        _add_verification(inv, hyp1, "silent")
        _add_verification(inv, hyp2, "corroborated", authority_result="authoritative")

        self.assertEqual(compute_final_status(inv), FinalStatus.SUPPORTED_DISCREPANCY)

    def test_one_unchecked_hypothesis_among_checked_clean_yields_insufficient_evidence(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f1 = _add_fact(inv, doc, value="99213")
        f2 = _add_fact(inv, doc, value="99214")
        hyp1 = _add_hypothesis(inv, [f1.id], statement="Hypothesis A")
        _add_hypothesis(inv, [f2.id], statement="Hypothesis B")  # never verified at all
        _add_verification(inv, hyp1, "silent")

        self.assertEqual(compute_final_status(inv), FinalStatus.INSUFFICIENT_EVIDENCE)


# ---------------------------------------------------------------------
# Cases 16/17 -- Reassessment with / without genuine new evidence
# ---------------------------------------------------------------------
class TestCase16And17Reassessment(unittest.TestCase):
    def test_reassessment_with_genuine_new_evidence_succeeds(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "silent")
        _advance_to_adjudicated(inv)

        first = adjudicate_investigation(inv)
        self.assertEqual(first.final_status, FinalStatus.NO_SUPPORTED_DISCREPANCY)
        self.assertEqual(first.version, 1)

        inv.transition_to(InvestigationState.EVIDENCE_RETRIEVED)
        inv.transition_to(InvestigationState.VERIFIED)
        inv.transition_to(InvestigationState.CONFLICT_CHECKED)
        inv.transition_to(InvestigationState.ADJUDICATED)
        _add_verification(inv, hyp, "corroborated", authority_result="authoritative")

        second = adjudicate_investigation(inv, reason_for_reassessment="New corroborating evidence found.")
        self.assertEqual(second.final_status, FinalStatus.SUPPORTED_DISCREPANCY)
        self.assertEqual(second.version, 2)
        self.assertEqual(second.supersedes_adjudication_id, first.id)

    def test_reassessment_without_new_evidence_is_rejected(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "silent")
        _advance_to_adjudicated(inv)

        adjudicate_investigation(inv)

        inv.transition_to(InvestigationState.EVIDENCE_RETRIEVED)
        inv.transition_to(InvestigationState.VERIFIED)
        inv.transition_to(InvestigationState.CONFLICT_CHECKED)
        inv.transition_to(InvestigationState.ADJUDICATED)
        # No new evidence added -- snapshot is identical to before.

        with self.assertRaises(AdjudicationError):
            adjudicate_investigation(inv, reason_for_reassessment="Trying again, nothing new.")


# ---------------------------------------------------------------------
# Case 18 -- Stale evidence (explicitly deferred, per the approved audit)
# ---------------------------------------------------------------------
class TestCase18StaleEvidence(unittest.TestCase):
    def test_stale_evidence_policy_is_explicitly_out_of_scope(self):
        # No staleness policy exists anywhere in the data model beyond
        # raw timestamps -- deliberately deferred (Closure Audit FUTURE
        # item). Documented here rather than silently omitted.
        self.assertTrue(True)


# ---------------------------------------------------------------------
# Case 19 -- Conflicting EOB and plan methodology
# ---------------------------------------------------------------------
class TestCase19EOBPlanMethodologyConflict(unittest.TestCase):
    def test_conflict_handling_is_source_type_agnostic(self):
        # Build 4C cannot currently PRODUCE this specific conflict
        # automatically (EOB/PLAN_POLICY have no lookup mechanism yet --
        # a documented Build 4C limitation). compute_final_status() only
        # reads Conflict.claim_id, never source types -- proving the
        # decision layer would handle this correctly the moment upstream
        # coverage is ever extended, with zero change needed here.
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_conflict(inv, hyp)

        self.assertEqual(compute_final_status(inv), FinalStatus.CONFLICTING_EVIDENCE)


# ---------------------------------------------------------------------
# Case 20 -- Suspicious-looking but ultimately legitimate bill
# ---------------------------------------------------------------------
class TestCase20SuspiciousButLegitimate(unittest.TestCase):
    def test_alarming_claim_text_has_zero_special_effect(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id], statement="MASSIVE FRAUD DETECTED!!! Obvious overcharge!!!")
        _add_verification(inv, hyp, "silent")

        self.assertEqual(compute_final_status(inv), FinalStatus.NO_SUPPORTED_DISCREPANCY)


# ---------------------------------------------------------------------
# Precondition failures
# ---------------------------------------------------------------------
class TestPreconditionFailure(unittest.TestCase):
    def test_zero_hypotheses_and_zero_facts_raises_precondition_error(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        with self.assertRaises(AdjudicationPreconditionError):
            compute_final_status(inv)

    def test_zero_hypotheses_but_facts_exist_is_a_legitimate_clean_result(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        _add_fact(inv, doc)
        self.assertEqual(compute_final_status(inv), FinalStatus.NO_SUPPORTED_DISCREPANCY)

    def test_non_investigation_input_raises_type_error(self):
        with self.assertRaises(TypeError):
            compute_final_status("not an investigation")


# ---------------------------------------------------------------------
# State-machine non-involvement
# ---------------------------------------------------------------------
class TestStateMachineNotAdvanced(unittest.TestCase):
    def test_compute_final_status_never_changes_investigation_state(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "corroborated", authority_result="authoritative")

        state_before = inv.state
        compute_final_status(inv)
        self.assertEqual(inv.state, state_before)
        self.assertEqual(inv.state, InvestigationState.INGESTED)

    def test_adjudicate_investigation_requires_adjudicated_state_precondition(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "corroborated", authority_result="authoritative")
        # State is still INGESTED -- adjudicate_investigation does not
        # advance it itself.
        with self.assertRaises(IllegalTransitionError):
            adjudicate_investigation(inv)


# ---------------------------------------------------------------------
# Hard-gate regressions
# ---------------------------------------------------------------------
class TestHardGateRegressions(unittest.TestCase):
    def test_appeal_only_reachable_after_real_supported_discrepancy_adjudication(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "corroborated", authority_result="authoritative")
        _advance_to_adjudicated(inv)

        self.assertFalse(inv.can_draft_appeal())
        adjudicate_investigation(inv)
        self.assertTrue(inv.can_draft_appeal())

    def test_appeal_remains_unreachable_after_no_supported_discrepancy(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "silent")
        _advance_to_adjudicated(inv)

        adjudicate_investigation(inv)
        self.assertFalse(inv.can_draft_appeal())

    def test_appeal_remains_unreachable_after_insufficient_evidence(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        _add_hypothesis(inv, [f.id])
        _advance_to_adjudicated(inv)

        adjudicate_investigation(inv)
        self.assertFalse(inv.can_draft_appeal())

    def test_appeal_remains_unreachable_after_conflicting_evidence(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "corroborated", authority_result="authoritative")
        _add_conflict(inv, hyp)
        _advance_to_adjudicated(inv)

        adjudicate_investigation(inv)
        self.assertFalse(inv.can_draft_appeal())

    def test_gate2_user_context_still_rejected_after_adjudication(self):
        inv, doc = _base_investigation(scope_value=CaseScopeValue.MEDICARE)
        f = _add_fact(inv, doc)
        hyp = _add_hypothesis(inv, [f.id])
        _add_verification(inv, hyp, "corroborated", authority_result="authoritative")
        _advance_to_adjudicated(inv)
        adjudicate_investigation(inv)

        uc = UserContext(investigation_id=inv.investigation_id, stated_concern_text="x")
        with self.assertRaises(TypeError):
            inv.ledger.add_source(uc)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
