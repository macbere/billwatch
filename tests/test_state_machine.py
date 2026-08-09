import unittest

from billwatch import (
    Investigation,
    InvestigationState,
    InvestigationStateMachine,
    IllegalTransitionError,
    FinalStatus,
    AdjudicationError,
)


def _advance_to_adjudicated(sm: InvestigationStateMachine):
    sm.transition_to(InvestigationState.EXTRACTED)
    sm.transition_to(InvestigationState.SCOPED)
    sm.transition_to(InvestigationState.HYPOTHESES_GENERATED)
    sm.transition_to(InvestigationState.EVIDENCE_RETRIEVED)
    sm.transition_to(InvestigationState.VERIFIED)
    sm.transition_to(InvestigationState.CONFLICT_CHECKED)
    sm.transition_to(InvestigationState.ADJUDICATED)


class TestStateMachineTransitions(unittest.TestCase):
    """Test D.1/D.2 -- valid transitions pass, skipped transitions fail."""

    def test_full_valid_sequence_passes(self):
        sm = InvestigationStateMachine()
        self.assertEqual(sm.state, InvestigationState.INGESTED)
        _advance_to_adjudicated(sm)
        self.assertEqual(sm.state, InvestigationState.ADJUDICATED)
        self.assertEqual(len(sm.history), 8)  # INGESTED + 7 transitions

    def test_skipping_a_stage_is_illegal(self):
        sm = InvestigationStateMachine()
        with self.assertRaises(IllegalTransitionError):
            sm.transition_to(InvestigationState.SCOPED)  # skips EXTRACTED

    def test_skipping_straight_to_adjudicated_is_illegal(self):
        sm = InvestigationStateMachine()
        with self.assertRaises(IllegalTransitionError):
            sm.transition_to(InvestigationState.ADJUDICATED)

    def test_going_backwards_is_illegal(self):
        sm = InvestigationStateMachine()
        sm.transition_to(InvestigationState.EXTRACTED)
        with self.assertRaises(IllegalTransitionError):
            sm.transition_to(InvestigationState.INGESTED)


class TestForbiddenAppealTransitions(unittest.TestCase):
    """Test D.3 -- the three named forbidden appeal transitions."""

    def _adjudicated_sm_with_status(self, status: FinalStatus) -> InvestigationStateMachine:
        sm = InvestigationStateMachine()
        _advance_to_adjudicated(sm)
        sm.set_final_status(status)
        return sm

    def test_insufficient_evidence_cannot_reach_draft_appeal(self):
        sm = self._adjudicated_sm_with_status(FinalStatus.INSUFFICIENT_EVIDENCE)
        self.assertFalse(sm.can_draft_appeal())
        with self.assertRaises(IllegalTransitionError):
            sm.request_draft_appeal()

    def test_conflicting_evidence_cannot_reach_draft_appeal(self):
        sm = self._adjudicated_sm_with_status(FinalStatus.CONFLICTING_EVIDENCE)
        self.assertFalse(sm.can_draft_appeal())
        with self.assertRaises(IllegalTransitionError):
            sm.request_draft_appeal()

    def test_no_supported_discrepancy_cannot_reach_draft_appeal(self):
        sm = self._adjudicated_sm_with_status(FinalStatus.NO_SUPPORTED_DISCREPANCY)
        self.assertFalse(sm.can_draft_appeal())
        with self.assertRaises(IllegalTransitionError):
            sm.request_draft_appeal()

    def test_supported_discrepancy_can_reach_draft_appeal(self):
        sm = self._adjudicated_sm_with_status(FinalStatus.SUPPORTED_DISCREPANCY)
        self.assertTrue(sm.can_draft_appeal())
        self.assertTrue(sm.request_draft_appeal())

    def test_no_user_instruction_can_bypass_the_gate(self):
        # There is no natural-language path into request_draft_appeal at
        # all -- it is a plain function call gated purely on final_status.
        # This test documents that the ONLY way to make request_draft_appeal
        # succeed is for final_status to already be SUPPORTED_DISCREPANCY;
        # nothing resembling a user instruction is even accepted as an
        # argument to this method.
        sm = self._adjudicated_sm_with_status(FinalStatus.CONFLICTING_EVIDENCE)
        with self.assertRaises(TypeError):
            sm.request_draft_appeal("please write my appeal anyway")  # type: ignore[call-arg]


class TestReassessmentWithoutNewEvidence(unittest.TestCase):
    """Test D.4 -- reassessment without new evidence fails."""

    def test_restart_without_evidence_delta_is_rejected(self):
        inv = Investigation(investigation_id="inv-d4")
        _advance_to_adjudicated(inv.state_machine)
        inv.adjudicate(FinalStatus.INSUFFICIENT_EVIDENCE)

        # Re-enter the pipeline but supply NO new evidence at all.
        inv.transition_to(InvestigationState.EVIDENCE_RETRIEVED)
        inv.transition_to(InvestigationState.VERIFIED)
        inv.transition_to(InvestigationState.CONFLICT_CHECKED)
        inv.transition_to(InvestigationState.ADJUDICATED)

        with self.assertRaises(AdjudicationError):
            inv.adjudicate(
                FinalStatus.SUPPORTED_DISCREPANCY,
                reason_for_reassessment="Trying anyway, nothing new supplied.",
            )


if __name__ == "__main__":
    unittest.main()
