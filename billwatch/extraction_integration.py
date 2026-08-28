"""
Build 4A: Extraction Integration.

Connects the already-built, already-tested extraction orchestrator
(extraction.py) into the real Investigation/EvidenceLedger pipeline.
Reuses, without modifying: extraction.py, llm_schemas.py, llm_provider.py,
evidence.py, investigation.py, and all three hard gates.

Flow:
    Document (must already be registered in Investigation.ledger)
        -> extraction.extract_from_document()        [REUSED, unmodified]
            -> LLMProvider.complete_json()            [REUSED, unmodified]
            -> llm_schemas.parse_extraction_candidate()  [REUSED, unmodified]
        -> deterministic acceptance (this module, new)
        -> EvidenceLedger.add_fact()                  [REUSED, unmodified]

This module makes NO domain decision -- it never touches CaseScope,
authority, FinalStatus, or appeal eligibility. It only ever converts an
already-validated ExtractedFactCandidate (llm_schemas.py already rejected
anything hallucinated, out-of-contract, or domain-decision-shaped) into a
real ExtractedFact and records it. Rejected facts are reported, never
silently added.
"""

from dataclasses import dataclass
from typing import Optional

from .evidence import Document, ExtractedFact
from .investigation import Investigation
from .user_context import UserContext
from .llm_provider import LLMProvider
from .extraction import extract_from_document, ExtractionOutcome


class ExtractionIntegrationError(Exception):
    """Raised for integration-layer misuse -- e.g. a Document that was
    never registered in this Investigation's ledger, or a caller passing
    something other than a real Document. Distinct from LLMProviderError
    and SchemaValidationError, which cover provider/validation failures,
    not caller misuse. This is a defense-in-depth re-check consistent
    with Gate 2's existing pattern of guarding at more than one layer."""


@dataclass(frozen=True)
class ExtractionIntegrationResult:
    success: bool
    document_id: str
    fact_ids_added: tuple = ()
    rejected_fact_count: int = 0
    rejected_reasons: tuple = ()
    failure_stage: Optional[str] = None   # None | "registration" | "provider" | "validation"
    failure_reason: Optional[str] = None


def integrate_extraction(
    investigation: Investigation,
    document: Document,
    provider: LLMProvider,
) -> ExtractionIntegrationResult:
    if isinstance(document, UserContext):
        raise ExtractionIntegrationError(
            "UserContext cannot be used as a Document for extraction -- "
            "the user's stated concern is not a document to extract facts "
            "from (Gate 2, re-enforced at this integration boundary)."
        )
    if not isinstance(document, Document):
        raise ExtractionIntegrationError(
            f"Expected Document, got {type(document).__name__}"
        )

    known_document_ids = {d.id for d in investigation.ledger.documents}
    if document.id not in known_document_ids:
        return ExtractionIntegrationResult(
            success=False,
            document_id=document.id,
            failure_stage="registration",
            failure_reason=(
                f"Document {document.id!r} is not registered in this "
                "investigation's EvidenceLedger. Call "
                "investigation.ledger.add_document(document) before "
                "extracting from it."
            ),
        )

    outcome: ExtractionOutcome = extract_from_document(document, provider)

    if not outcome.success:
        return ExtractionIntegrationResult(
            success=False,
            document_id=document.id,
            failure_stage=outcome.failure_stage,
            failure_reason=outcome.failure_reason,
        )

    added_ids = []
    for candidate in outcome.candidate.accepted_facts:
        fact = ExtractedFact(
            document_id=document.id,
            fact_type=candidate.fact_type,
            value=candidate.value,
            confidence=candidate.confidence,
            source_span=candidate.source_span,
        )
        investigation.ledger.add_fact(fact)
        added_ids.append(fact.id)

    return ExtractionIntegrationResult(
        success=True,
        document_id=document.id,
        fact_ids_added=tuple(added_ids),
        rejected_fact_count=len(outcome.candidate.rejected_facts),
        rejected_reasons=tuple(r.reason for r in outcome.candidate.rejected_facts),
    )
