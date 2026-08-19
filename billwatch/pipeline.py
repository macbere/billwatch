"""
Build 4F: Orchestration Pipeline.

The orchestrator is a TRAFFIC CONTROLLER, not a sixth reasoning engine.
It sequences the five existing, unmodified bounded components:

    extraction_integration.integrate_extraction()
    hypothesis_integration.generate_and_record_hypothesis()
    verification_integration.verify_hypothesis()
    adjudication_integration.adjudicate_investigation()
    appeal_integration.generate_appeal_draft()

and, for the first time in production code (not just test fixtures),
owns the Investigation state-machine transitions between them.

FAIL-CLOSED SEMANTICS: a transition to the next stage only ever happens
after the corresponding prior stage has genuinely succeeded. On any
failure, the pipeline stops immediately and returns a PipelineResult
describing exactly which stage failed and why -- it never proceeds to
adjudicate on incomplete verification, and it never attempts appeal
generation unless final_status == SUPPORTED_DISCREPANCY.

The orchestrator NEVER accepts a caller-supplied final_status -- there
is no such parameter anywhere in this module. FinalStatus comes only
from adjudicate_investigation() (Build 4D), which itself never accepts
LLM input of any kind. Gemini's only role anywhere in this pipeline is
generating the structured field proposals that extraction/hypothesis/
verification/appeal already validate deterministically -- exactly as
established in every prior build.

DESIGN NOTE on EVIDENCE_RETRIEVED/VERIFIED: the current architecture
has no separately-callable "retrieve evidence" step distinct from
"verify it" -- verify_hypothesis() does both atomically in one call.
Rather than transitioning to EVIDENCE_RETRIEVED speculatively before
knowing whether verification will succeed, this orchestrator calls
verify_hypothesis() first, and only on success fires
EVIDENCE_RETRIEVED -> VERIFIED -> CONFLICT_CHECKED in sequence.

DESIGN NOTE on ADJUDICATED: transitioning into the ADJUDICATED state is
itself just entering that node in the state graph (per state_machine.py's
own design) -- it is not, by itself, a claim that adjudication produced
any particular outcome. This transition happens once verification has
genuinely succeeded (CONFLICT_CHECKED reached); the actual FinalStatus
is then computed and recorded, within that state, by
adjudicate_investigation().

DESIGN SIMPLIFICATION (documented, not hidden): this orchestrator
generates exactly ONE hypothesis per run. Multiple-hypothesis handling
is already proven correct at the component level (Build 4B/4D), but a
multi-hypothesis orchestration loop is out of this fast-track build's
minimal scope.
"""

from dataclasses import dataclass
from typing import Optional

from .adjudication_integration import AdjudicationPreconditionError, adjudicate_investigation
from .appeal_integration import AppealDraftResult, generate_appeal_draft
from .case_scope import CaseScope
from .enums import FinalStatus, InvestigationState
from .evidence import Document
from .extraction_integration import ExtractionIntegrationResult, integrate_extraction
from .hypothesis_integration import generate_and_record_hypothesis
from .investigation import Investigation
from .llm_provider import LLMProvider
from .reference_data import ReferenceStore
from .verification_integration import VerificationIntegrationResult, verify_hypothesis


class PipelineError(Exception):
    """Raised for orchestrator-level misuse -- e.g. calling this with
    something other than a fresh Investigation."""


@dataclass(frozen=True)
class PipelineResult:
    success: bool
    investigation_id: str
    failed_stage: Optional[str] = None   # None | "extraction" | "hypothesis" | "verification" | "adjudication"
    failure_reason: Optional[str] = None
    final_status: Optional[FinalStatus] = None
    hypothesis_id: Optional[str] = None
    extraction_results: tuple = ()
    verification_result: Optional[VerificationIntegrationResult] = None
    appeal: Optional[AppealDraftResult] = None


def run_investigation(
    investigation: Investigation,
    documents,
    case_scope: Optional[CaseScope],
    provider: LLMProvider,
    reference_store: ReferenceStore,
) -> PipelineResult:
    if not isinstance(investigation, Investigation):
        raise PipelineError(f"Expected Investigation, got {type(investigation).__name__}")
    if investigation.state != InvestigationState.INGESTED:
        raise PipelineError(
            f"run_investigation requires a fresh Investigation in INGESTED "
            f"state, got {investigation.state.value}"
        )

    # -- Extraction (fail-closed: any document failing stops the pipeline) --
    extraction_results = []
    for doc in documents:
        if not isinstance(doc, Document):
            raise PipelineError(f"Expected Document, got {type(doc).__name__}")
        investigation.ledger.add_document(doc)
        result = integrate_extraction(investigation, doc, provider)
        extraction_results.append(result)
        if not result.success:
            return PipelineResult(
                success=False, investigation_id=investigation.investigation_id,
                failed_stage="extraction", failure_reason=result.failure_reason,
                extraction_results=tuple(extraction_results),
            )
    investigation.transition_to(InvestigationState.EXTRACTED)

    # -- Scope (deterministic plumbing only -- never resolved here) --
    if case_scope is not None:
        investigation.set_case_scope(case_scope)
    investigation.transition_to(InvestigationState.SCOPED)

    # -- Hypothesis --
    hyp_result = generate_and_record_hypothesis(investigation, provider)
    if not hyp_result.success:
        return PipelineResult(
            success=False, investigation_id=investigation.investigation_id,
            failed_stage="hypothesis", failure_reason=hyp_result.failure_reason,
            extraction_results=tuple(extraction_results),
        )
    investigation.transition_to(InvestigationState.HYPOTHESES_GENERATED)

    # -- Verification --
    ver_result = verify_hypothesis(investigation, hyp_result.hypothesis_id, provider, reference_store)
    if not ver_result.success:
        return PipelineResult(
            success=False, investigation_id=investigation.investigation_id,
            failed_stage="verification", failure_reason=ver_result.failure_reason,
            extraction_results=tuple(extraction_results), hypothesis_id=hyp_result.hypothesis_id,
        )
    investigation.transition_to(InvestigationState.EVIDENCE_RETRIEVED)
    investigation.transition_to(InvestigationState.VERIFIED)
    investigation.transition_to(InvestigationState.CONFLICT_CHECKED)

    # -- Adjudication --
    investigation.transition_to(InvestigationState.ADJUDICATED)
    try:
        adjudication = adjudicate_investigation(investigation)
    except AdjudicationPreconditionError as exc:
        return PipelineResult(
            success=False, investigation_id=investigation.investigation_id,
            failed_stage="adjudication", failure_reason=str(exc),
            extraction_results=tuple(extraction_results), hypothesis_id=hyp_result.hypothesis_id,
            verification_result=ver_result,
        )

    final_status = adjudication.final_status

    # -- Appeal (conditional -- Gate 3 inside appeal_integration.py remains
    #    the actual enforcement; this check is a convenience short-circuit,
    #    not a substitute security boundary) --
    appeal_result = None
    if final_status == FinalStatus.SUPPORTED_DISCREPANCY:
        appeal_result = generate_appeal_draft(investigation, provider)

    return PipelineResult(
        success=True,
        investigation_id=investigation.investigation_id,
        final_status=final_status,
        hypothesis_id=hyp_result.hypothesis_id,
        extraction_results=tuple(extraction_results),
        verification_result=ver_result,
        appeal=appeal_result,
    )
