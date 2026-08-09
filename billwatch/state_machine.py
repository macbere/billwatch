"""
Investigation State Machine (Build 1, Section 5).

This is the concrete, code-level enforcement of Gate 3 (Appeal Eligibility)
and the general "no bypassable state transitions" invariant from the
approved architecture. It contains no LLM calls and no external API calls
-- it is pure control-flow logic over an explicit transition table.
"""

from datetime import datetime, timezone
from typing import Optional

from .enums import InvestigationState, FinalStatus


class IllegalTransitionError(Exception):
    """Raised whenever a transition is attempted that the transition table
    does not explicitly allow, or whenever DRAFT_APPEAL is requested from
    a final_status other than SUPPORTED_DISCREPANCY."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# The exhaustive set of legal transitions. Anything not listed here is
# illegal by default -- this is a deliberate allow-list, not a deny-list,
# so a forgotten forbidden transition can never accidentally become legal.
LEGAL_TRANSITIONS = {
    InvestigationState.INGESTED: {InvestigationState.EXTRACTED},
    InvestigationState.EXTRACTED: {InvestigationState.SCOPED},
    InvestigationState.SCOPED: {InvestigationState.HYPOTHESES_GENERATED},
    InvestigationState.HYPOTHESES_GENERATED: {InvestigationState.EVIDENCE_RETRIEVED},
    InvestigationState.EVIDENCE_RETRIEVED: {InvestigationState.VERIFIED},
    InvestigationState.VERIFIED: {InvestigationState.CONFLICT_CHECKED},
    InvestigationState.CONFLICT_CHECKED: {InvestigationState.ADJUDICATED},
    # The ONLY legal way out of ADJUDICATED is the restart path, which
    # re-enters the pipeline at EVIDENCE_RETRIEVED and must traverse
    # VERIFIED -> CONFLICT_CHECKED -> ADJUDICATED again in full before a
    # new final_status can be set (Adjudication's own evidence-delta guard
    # applies on top of this). There is no shortcut back to ADJUDICATED.
    InvestigationState.ADJUDICATED: {InvestigationState.EVIDENCE_RETRIEVED},
}


class InvestigationStateMachine:
    def __init__(self):
        self.state: InvestigationState = InvestigationState.INGESTED
        self.final_status: Optional[FinalStatus] = None
        self._history = [(InvestigationState.INGESTED, _now())]

    @property
    def history(self) -> tuple:
        return tuple(self._history)

    def transition_to(self, new_state: InvestigationState) -> None:
        allowed = LEGAL_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise IllegalTransitionError(
                f"Illegal transition: {self.state.value} -> {new_state.value}. "
                f"Legal transitions from {self.state.value} are: "
                f"{sorted(s.value for s in allowed) or 'none'}."
            )
        self.state = new_state
        self._history.append((new_state, _now()))
        if new_state != InvestigationState.ADJUDICATED:
            # Re-entering the pipeline for a restart clears the previous
            # final_status until a new ADJUDICATED state sets a fresh one --
            # it is never left dangling from a prior version.
            self.final_status = None

    def set_final_status(self, status: FinalStatus) -> None:
        if self.state != InvestigationState.ADJUDICATED:
            raise IllegalTransitionError(
                "final_status can only be set once state == ADJUDICATED "
                f"(current state: {self.state.value})."
            )
        if not isinstance(status, FinalStatus):
            raise TypeError(f"final_status must be a FinalStatus, got {type(status).__name__}")
        self.final_status = status

    # -- Gate 3 enforcement point ----------------------------------------
    def can_draft_appeal(self) -> bool:
        return (
            self.state == InvestigationState.ADJUDICATED
            and self.final_status == FinalStatus.SUPPORTED_DISCREPANCY
        )

    def request_draft_appeal(self) -> bool:
        """
        The single, structural chokepoint that Build-1's Gate 3 must prove:
        no code path -- and, critically, no natural-language user request
        in later builds -- can reach appeal drafting unless final_status is
        exactly SUPPORTED_DISCREPANCY. Build 1 does not implement appeal
        generation itself; this method only proves the gate cannot be
        bypassed.
        """
        if not self.can_draft_appeal():
            raise IllegalTransitionError(
                "DRAFT_APPEAL is unreachable: final_status is "
                f"{self.final_status.value if self.final_status else None!r}. "
                "Appeal drafting requires final_status == SUPPORTED_DISCREPANCY."
            )
        return True
