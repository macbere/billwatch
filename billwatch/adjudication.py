"""
Adjudication versioning (Build 1, Section 4 / Phase 3.3A Correction 3).

Adjudications are append-only. A previous adjudication is NEVER edited --
every reassessment is a new, explicitly-justified version that supersedes
the last. Adjudication itself is a frozen dataclass, so attempting to
mutate one raises dataclasses.FrozenInstanceError; Investigation only ever
exposes its adjudication history as an immutable tuple, and the only way
to add a new one is through the two guarded methods below.
"""

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

from .enums import FinalStatus


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AdjudicationError(Exception):
    """Raised when an adjudication operation would violate append-only /
    evidence-delta / immutability rules."""


@dataclass(frozen=True)
class Adjudication:
    investigation_id: str
    version: int
    evidence_snapshot: dict
    final_status: FinalStatus
    id: str = field(default_factory=_new_id)
    created_at: datetime = field(default_factory=_now)
    supersedes_adjudication_id: Optional[str] = None
    reason_for_reassessment: Optional[str] = None

    # Kept as a convenience alias matching the spec's field name exactly.
    @property
    def adjudication_id(self) -> str:
        return self.id


class _AdjudicationHistoryMixin:
    """
    Append-only adjudication history behavior, mixed into Investigation
    (investigation.py). Kept in this module so Adjudication and its
    invariants live in one place, but the composed Investigation facade
    (which also owns the EvidenceLedger, UserContext, CaseScope, and
    InvestigationStateMachine) lives in investigation.py.
    """

    def _init_adjudication_history(self):
        self._adjudications: list = []
        self.current_adjudication_id: Optional[str] = None

    @property
    def adjudications(self) -> tuple:
        return tuple(self._adjudications)

    @property
    def current_adjudication(self) -> Optional[Adjudication]:
        if self.current_adjudication_id is None:
            return None
        return self.get_adjudication(self.current_adjudication_id)

    def get_adjudication(self, adjudication_id: str) -> Optional[Adjudication]:
        for a in self._adjudications:
            if a.id == adjudication_id:
                return a
        return None

    def add_first_adjudication(self, evidence_snapshot: dict, final_status: FinalStatus) -> Adjudication:
        if self._adjudications:
            raise AdjudicationError(
                "Investigation already has an adjudication. Use "
                "restart_with_new_evidence() to add a superseding version."
            )
        adj = Adjudication(
            investigation_id=self.investigation_id,
            version=1,
            evidence_snapshot=evidence_snapshot,
            final_status=final_status,
            supersedes_adjudication_id=None,
            reason_for_reassessment=None,
        )
        self._adjudications.append(adj)
        self.current_adjudication_id = adj.id
        return adj

    def restart_with_new_evidence(
        self,
        new_evidence_snapshot: dict,
        final_status: FinalStatus,
        reason_for_reassessment: str,
    ) -> Adjudication:
        """
        The ONLY way to produce a new adjudication after the first. Guarded
        so that:
          - it cannot run before a first adjudication exists;
          - it is rejected outright if the evidence snapshot hasn't
            actually changed (no silent re-rolls);
          - reason_for_reassessment is mandatory and non-empty.
        """
        if not self._adjudications:
            raise AdjudicationError(
                "No prior adjudication exists to supersede; call "
                "add_first_adjudication() first."
            )
        previous = self._adjudications[-1]
        if new_evidence_snapshot == previous.evidence_snapshot:
            raise AdjudicationError(
                "Restart rejected: no evidence delta detected compared to "
                "the previous adjudication. Reassessment requires genuinely "
                "new evidence."
            )
        if not reason_for_reassessment or not reason_for_reassessment.strip():
            raise AdjudicationError(
                "Restart rejected: reason_for_reassessment is required and "
                "must be non-empty."
            )
        adj = Adjudication(
            investigation_id=self.investigation_id,
            version=previous.version + 1,
            evidence_snapshot=new_evidence_snapshot,
            final_status=final_status,
            supersedes_adjudication_id=previous.id,
            reason_for_reassessment=reason_for_reassessment.strip(),
        )
        self._adjudications.append(adj)
        self.current_adjudication_id = adj.id
        return adj

    @staticmethod
    def assert_immutable(adjudication: Adjudication, **attempted_changes) -> None:
        """
        Helper used by tests to demonstrate that an existing Adjudication
        cannot be mutated. Any attribute assignment on a frozen dataclass
        raises dataclasses.FrozenInstanceError; this helper just makes that
        explicit and reusable rather than duplicating try/except in tests.
        """
        for attr, value in attempted_changes.items():
            try:
                setattr(adjudication, attr, value)
            except dataclasses.FrozenInstanceError:
                continue
            else:
                raise AssertionError(
                    f"Adjudication.{attr} was mutated -- immutability is broken."
                )
