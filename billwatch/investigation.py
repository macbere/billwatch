"""
Investigation (Build 1, Section 2 + composition root).

Investigation is the single object representing one bill investigation. It
composes, but deliberately does not merge, four distinct concerns:

  - EvidenceLedger   (the evidence -- Sources, Hypotheses, Verifications...)
  - UserContext      (the user's own narrative -- explicitly NOT evidence)
  - CaseScope        (how Medicare/Medicaid/private scope was established)
  - InvestigationStateMachine (what stage the pipeline is in, and the
                                Gate 3 appeal-eligibility chokepoint)
  - adjudication history (append-only, via _AdjudicationHistoryMixin)

Keeping these as separate, composed objects -- rather than one flat bag of
fields -- is itself part of the structural enforcement: UserContext simply
has no path into EvidenceLedger's API (see evidence.py's add_source guard),
and CaseScope has no path into the state machine except through the
deterministic resolvers in case_scope.py.
"""

from typing import Optional
import uuid

from .adjudication import _AdjudicationHistoryMixin, AdjudicationError
from .case_scope import CaseScope
from .enums import InvestigationState
from .evidence import EvidenceLedger
from .state_machine import InvestigationStateMachine, IllegalTransitionError
from .user_context import UserContext


class Investigation(_AdjudicationHistoryMixin):
    def __init__(self, investigation_id: str = None):
        self.investigation_id = investigation_id or str(uuid.uuid4())
        self.ledger = EvidenceLedger()
        self.state_machine = InvestigationStateMachine()
        self.user_context: Optional[UserContext] = None
        self.case_scope: Optional[CaseScope] = None
        self._init_adjudication_history()

    # -- UserContext -------------------------------------------------
    def set_user_context(self, user_context: UserContext) -> None:
        if not isinstance(user_context, UserContext):
            raise TypeError(
                f"set_user_context requires a UserContext, got {type(user_context).__name__}"
            )
        if user_context.investigation_id != self.investigation_id:
            raise ValueError(
                "UserContext.investigation_id does not match this Investigation."
            )
        self.user_context = user_context

    # -- CaseScope -----------------------------------------------------
    def set_case_scope(self, case_scope: CaseScope) -> None:
        if not isinstance(case_scope, CaseScope):
            raise TypeError(
                f"set_case_scope requires a CaseScope, got {type(case_scope).__name__}"
            )
        self.case_scope = case_scope

    # -- State machine passthroughs -------------------------------------
    @property
    def state(self) -> InvestigationState:
        return self.state_machine.state

    @property
    def final_status(self):
        return self.state_machine.final_status

    def transition_to(self, new_state: InvestigationState) -> None:
        self.state_machine.transition_to(new_state)

    def set_final_status(self, status) -> None:
        self.state_machine.set_final_status(status)

    def can_draft_appeal(self) -> bool:
        return self.state_machine.can_draft_appeal()

    def request_draft_appeal(self) -> bool:
        return self.state_machine.request_draft_appeal()

    # -- Convenience: adjudicate using the current ledger snapshot -------
    def adjudicate(self, final_status, reason_for_reassessment: str = None):
        """
        Records the current state_machine.final_status as a new
        Adjudication (v1 if none exists yet, otherwise a superseding
        version via the restart path). Requires state == ADJUDICATED,
        consistent with the state machine's own set_final_status rule.
        """
        if self.state_machine.state != InvestigationState.ADJUDICATED:
            raise IllegalTransitionError(
                "Cannot adjudicate: state machine is not in ADJUDICATED "
                f"(current: {self.state_machine.state.value})."
            )
        self.set_final_status(final_status)
        snapshot = self.ledger.snapshot()
        if not self._adjudications:
            return self.add_first_adjudication(snapshot, final_status)
        return self.restart_with_new_evidence(snapshot, final_status, reason_for_reassessment)
