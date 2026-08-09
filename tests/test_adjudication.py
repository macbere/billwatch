import dataclasses
import unittest

from billwatch import Investigation, FinalStatus, InvestigationState, AdjudicationError


def _advance_to_adjudicated(inv: Investigation):
    inv.transition_to(InvestigationState.EXTRACTED)
    inv.transition_to(InvestigationState.SCOPED)
    inv.transition_to(InvestigationState.HYPOTHESES_GENERATED)
    inv.transition_to(InvestigationState.EVIDENCE_RETRIEVED)
    inv.transition_to(InvestigationState.VERIFIED)
    inv.transition_to(InvestigationState.CONFLICT_CHECKED)
    inv.transition_to(InvestigationState.ADJUDICATED)


class TestAdjudicationVersioning(unittest.TestCase):
    """Test C -- Adjudication versioning (7 required checks)."""

    def test_full_versioning_lifecycle(self):
        inv = Investigation(investigation_id="inv-c")

        # 1. First adjudication = v1
        _advance_to_adjudicated(inv)
        v1 = inv.adjudicate(FinalStatus.INSUFFICIENT_EVIDENCE)
        self.assertEqual(v1.version, 1)
        self.assertIsNone(v1.supersedes_adjudication_id)

        # 2. incomplete evidence -> INSUFFICIENT_EVIDENCE
        self.assertEqual(v1.final_status, FinalStatus.INSUFFICIENT_EVIDENCE)
        self.assertEqual(inv.final_status, FinalStatus.INSUFFICIENT_EVIDENCE)

        # Simulate genuinely new evidence being supplied, then restart.
        inv.ledger.add_fact(_dummy_fact())
        inv.transition_to(InvestigationState.EVIDENCE_RETRIEVED)
        inv.transition_to(InvestigationState.VERIFIED)
        inv.transition_to(InvestigationState.CONFLICT_CHECKED)
        inv.transition_to(InvestigationState.ADJUDICATED)

        # 3. genuine new evidence -> v2
        v2 = inv.adjudicate(
            FinalStatus.SUPPORTED_DISCREPANCY,
            reason_for_reassessment="User supplied the missing plan document.",
        )
        self.assertEqual(v2.version, 2)

        # 4. v2 supersedes v1
        self.assertEqual(v2.supersedes_adjudication_id, v1.id)

        # 5. v1 remains unchanged
        v1_reloaded = inv.get_adjudication(v1.id)
        self.assertEqual(v1_reloaded.final_status, FinalStatus.INSUFFICIENT_EVIDENCE)
        self.assertEqual(v1_reloaded.version, 1)

        # 6. current_adjudication_id points to v2
        self.assertEqual(inv.current_adjudication_id, v2.id)
        self.assertEqual(inv.current_adjudication.id, v2.id)

        # 7. no-new-evidence restart is rejected
        with self.assertRaises(AdjudicationError):
            inv.restart_with_new_evidence(
                new_evidence_snapshot=inv.ledger.snapshot(),  # unchanged snapshot
                final_status=FinalStatus.SUPPORTED_DISCREPANCY,
                reason_for_reassessment="Trying to re-roll without new evidence.",
            )

        # Both versions remain independently queryable.
        self.assertEqual(len(inv.adjudications), 2)
        self.assertEqual({a.version for a in inv.adjudications}, {1, 2})

    def test_reassessment_requires_nonempty_reason(self):
        inv = Investigation(investigation_id="inv-c2")
        _advance_to_adjudicated(inv)
        inv.adjudicate(FinalStatus.INSUFFICIENT_EVIDENCE)

        inv.ledger.add_fact(_dummy_fact())
        inv.transition_to(InvestigationState.EVIDENCE_RETRIEVED)
        inv.transition_to(InvestigationState.VERIFIED)
        inv.transition_to(InvestigationState.CONFLICT_CHECKED)
        inv.transition_to(InvestigationState.ADJUDICATED)

        with self.assertRaises(AdjudicationError):
            inv.adjudicate(FinalStatus.SUPPORTED_DISCREPANCY, reason_for_reassessment="   ")


class TestAdjudicationImmutability(unittest.TestCase):
    """Test E -- attempting to mutate an existing adjudication is prevented."""

    def test_mutating_final_status_raises(self):
        inv = Investigation(investigation_id="inv-e")
        _advance_to_adjudicated(inv)
        v1 = inv.adjudicate(FinalStatus.NO_SUPPORTED_DISCREPANCY)

        with self.assertRaises(dataclasses.FrozenInstanceError):
            v1.final_status = FinalStatus.SUPPORTED_DISCREPANCY

    def test_mutating_version_raises(self):
        inv = Investigation(investigation_id="inv-e2")
        _advance_to_adjudicated(inv)
        v1 = inv.adjudicate(FinalStatus.NO_SUPPORTED_DISCREPANCY)

        with self.assertRaises(dataclasses.FrozenInstanceError):
            v1.version = 99

    def test_assert_immutable_helper(self):
        inv = Investigation(investigation_id="inv-e3")
        _advance_to_adjudicated(inv)
        v1 = inv.adjudicate(FinalStatus.NO_SUPPORTED_DISCREPANCY)
        # Should not raise -- confirms the helper correctly detects that
        # mutation is blocked rather than silently succeeding.
        Investigation.assert_immutable(v1, final_status=FinalStatus.CONFLICTING_EVIDENCE)


def _dummy_fact():
    from billwatch import ExtractedFact
    return ExtractedFact(document_id="doc-1", fact_type="code", value="45380")


if __name__ == "__main__":
    unittest.main()
