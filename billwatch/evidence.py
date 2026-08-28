"""
Evidence Data Model (Build 1, Section 2).

All entities are immutable (frozen dataclasses). Nothing here is ever
edited in place -- a "change" is always represented by adding a new,
distinct record, never by mutating an old one. This mirrors the
append-only philosophy applied to Adjudication (adjudication.py) and
keeps every entity independently auditable.

EvidenceLedger is the only place evidence enters an Investigation, and it
is the structural enforcement point for Gate 2 (UserContext separation):
add_source() explicitly rejects a UserContext instance, at runtime, not
merely via a type hint that could be ignored.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

from .enums import SourceType, AuthorityLevel
from .user_context import UserContext


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Document:
    doc_type: str  # "bill" | "eob" | "policy" | "addendum"
    raw_text: str
    id: str = field(default_factory=_new_id)
    upload_timestamp: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class ExtractedFact:
    document_id: str
    fact_type: str  # "line_item" | "code" | "date" | "amount" | "clause"
    value: str
    id: str = field(default_factory=_new_id)
    confidence: Optional[str] = None
    # Exact document substring already validated by llm_schemas.py before
    # integration. Optional for backward compatibility with facts created
    # directly by deterministic/test code predating provenance retention.
    source_span: Optional[str] = None


@dataclass(frozen=True)
class Source:
    """
    A single evidence source, per the Phase 3.2 corrected hierarchy.
    authority_level is assigned by Gate 1 logic (Build 2), never by the
    source itself and never by an LLM -- in Build 1 it defaults to None
    until a gate has actually classified it.
    """
    source_type: SourceType
    reference: str  # the specific citation, e.g. "NCCI edit table, 45378/45380"
    id: str = field(default_factory=_new_id)
    scope: Optional[str] = None
    license_usage_basis: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    authority_level: Optional[AuthorityLevel] = None


@dataclass(frozen=True)
class Claim:
    statement: str
    id: str = field(default_factory=_new_id)
    related_fact_ids: tuple = ()


@dataclass(frozen=True)
class Hypothesis:
    claim_id: str
    explanation_text: str
    id: str = field(default_factory=_new_id)
    referenced_fact_ids: tuple = ()


@dataclass(frozen=True)
class SupportingEvidence:
    hypothesis_id: str
    source_id: str
    cited_passage: str
    id: str = field(default_factory=_new_id)
    authority_level: Optional[AuthorityLevel] = None


@dataclass(frozen=True)
class ContradictoryEvidence:
    hypothesis_id: str
    source_id: str
    cited_passage: str
    id: str = field(default_factory=_new_id)
    authority_level: Optional[AuthorityLevel] = None


@dataclass(frozen=True)
class Verification:
    hypothesis_id: str
    corroboration_result: str  # "corroborated" | "contradicted" | "silent"
    citation_ref: Optional[str] = None
    authority_result: Optional[str] = None  # Build 4D correction: preserves
    # the actual AuthorityResult.value (e.g. "authoritative", "corroborating",
    # "admissible") that produced corroboration_result, so adjudication is
    # never forced to rely on a collapsed label alone. Optional/defaulted
    # for backward compatibility with any Verification constructed without it.
    id: str = field(default_factory=_new_id)


@dataclass(frozen=True)
class MissingEvidence:
    claim_id: str
    description: str
    id: str = field(default_factory=_new_id)


@dataclass(frozen=True)
class Conflict:
    claim_id: str
    source_a_id: str
    source_b_id: str
    what_each_says: str
    why_unresolved: str
    what_would_resolve_it: Optional[str] = None
    id: str = field(default_factory=_new_id)


class EvidenceLedger:
    """
    Append-only container for everything an investigation has gathered.

    This class is the structural enforcement point for Gate 2: add_source()
    raises TypeError if handed a UserContext (or anything that isn't a
    Source), so it is not merely discouraged but mechanically impossible
    for a caller to slip user narrative into the evidence set through this
    API.
    """

    _EVIDENCE_TYPES = (
        Document, ExtractedFact, Source, Claim, Hypothesis,
        SupportingEvidence, ContradictoryEvidence, Verification,
        MissingEvidence, Conflict,
    )

    def __init__(self):
        self._documents: list = []
        self._facts: list = []
        self._sources: list = []
        self._claims: list = []
        self._hypotheses: list = []
        self._supporting: list = []
        self._contradictory: list = []
        self._verifications: list = []
        self._missing_evidence: list = []
        self._conflicts: list = []

    # -- Build 2, Section 10: strengthened immutability -------------------
    @staticmethod
    def _reject_duplicate_id(existing_items, new_item, entity_name: str) -> None:
        """
        Every evidence entity is a frozen dataclass, so in-place attribute
        mutation already raises dataclasses.FrozenInstanceError (Build 1).
        This closes the remaining gap flagged as a Build 1 risk: it also
        refuses to let a caller add a *second* item sharing an existing
        item's id, since that would let someone smuggle a "changed" record
        past the frozen-field protection by re-inserting under the same
        identity. Any genuine change must be a new entity with a new id --
        never a same-id replacement.
        """
        existing_ids = {item.id for item in existing_items}
        if new_item.id in existing_ids:
            raise ValueError(
                f"{entity_name} with id={new_item.id!r} already exists in the "
                "ledger. Evidence entities are immutable and append-only: "
                "represent any change as a new entity with a new id, never "
                "by reusing an existing id."
            )

    # -- Gate 2 enforcement point -------------------------------------
    def add_source(self, source: Source) -> None:
        if isinstance(source, UserContext):
            raise TypeError(
                "UserContext cannot be added as evidence. The user's stated "
                "concern is not a Source and must never enter the evidence "
                "set used to establish a discrepancy (Gate 2)."
            )
        if not isinstance(source, Source):
            raise TypeError(f"Expected Source, got {type(source).__name__}")
        self._reject_duplicate_id(self._sources, source, "Source")
        self._sources.append(source)

    def add_document(self, document: Document) -> None:
        if isinstance(document, UserContext):
            raise TypeError("UserContext cannot be added as a Document.")
        if not isinstance(document, Document):
            raise TypeError(f"Expected Document, got {type(document).__name__}")
        self._reject_duplicate_id(self._documents, document, "Document")
        self._documents.append(document)

    def add_fact(self, fact: ExtractedFact) -> None:
        self._reject_duplicate_id(self._facts, fact, "ExtractedFact")
        self._facts.append(fact)

    def add_claim(self, claim: Claim) -> None:
        self._reject_duplicate_id(self._claims, claim, "Claim")
        self._claims.append(claim)

    def add_hypothesis(self, hypothesis: Hypothesis) -> None:
        # Every hypothesis must reference facts that actually exist in the
        # ledger (Phase 3.2 Section 3 rule) -- orphan hypotheses rejected.
        known_fact_ids = {f.id for f in self._facts}
        for fact_id in hypothesis.referenced_fact_ids:
            if fact_id not in known_fact_ids:
                raise ValueError(
                    f"Hypothesis references unknown fact_id={fact_id!r}; "
                    "orphan hypotheses are rejected."
                )
        self._reject_duplicate_id(self._hypotheses, hypothesis, "Hypothesis")
        self._hypotheses.append(hypothesis)

    def add_supporting_evidence(self, item: SupportingEvidence) -> None:
        self._reject_duplicate_id(self._supporting, item, "SupportingEvidence")
        self._supporting.append(item)

    def add_contradictory_evidence(self, item: ContradictoryEvidence) -> None:
        self._reject_duplicate_id(self._contradictory, item, "ContradictoryEvidence")
        self._contradictory.append(item)

    def add_verification(self, item: Verification) -> None:
        self._reject_duplicate_id(self._verifications, item, "Verification")
        self._verifications.append(item)

    def add_missing_evidence(self, item: MissingEvidence) -> None:
        self._reject_duplicate_id(self._missing_evidence, item, "MissingEvidence")
        self._missing_evidence.append(item)

    def add_conflict(self, item: Conflict) -> None:
        self._reject_duplicate_id(self._conflicts, item, "Conflict")
        self._conflicts.append(item)

    # -- read-only views -------------------------------------------------
    @property
    def documents(self) -> tuple:
        return tuple(self._documents)

    @property
    def facts(self) -> tuple:
        return tuple(self._facts)

    @property
    def sources(self) -> tuple:
        return tuple(self._sources)

    @property
    def claims(self) -> tuple:
        return tuple(self._claims)

    @property
    def hypotheses(self) -> tuple:
        return tuple(self._hypotheses)

    @property
    def supporting_evidence(self) -> tuple:
        return tuple(self._supporting)

    @property
    def contradictory_evidence(self) -> tuple:
        return tuple(self._contradictory)

    @property
    def verifications(self) -> tuple:
        return tuple(self._verifications)

    @property
    def missing_evidence(self) -> tuple:
        return tuple(self._missing_evidence)

    @property
    def conflicts(self) -> tuple:
        return tuple(self._conflicts)

    def snapshot(self) -> dict:
        """
        A deterministic, comparable summary of ledger state, used as
        Adjudication.evidence_snapshot and to detect whether a restart
        actually supplies a genuine evidence delta (Phase 3.3A Correction 3).
        """
        return {
            "documents": tuple(sorted(d.id for d in self._documents)),
            "facts": tuple(sorted(f.id for f in self._facts)),
            "sources": tuple(sorted(s.id for s in self._sources)),
            "claims": tuple(sorted(c.id for c in self._claims)),
            "hypotheses": tuple(sorted(h.id for h in self._hypotheses)),
            "supporting_evidence": tuple(sorted(s.id for s in self._supporting)),
            "contradictory_evidence": tuple(sorted(c.id for c in self._contradictory)),
            "verifications": tuple(sorted(v.id for v in self._verifications)),
            "missing_evidence": tuple(sorted(m.id for m in self._missing_evidence)),
            "conflicts": tuple(sorted(c.id for c in self._conflicts)),
        }
