"""
BillWatch -- Build 1: Evidence Data Model + State Machine.

No LLM calls, no external API calls, no UI. Pure, deterministic,
stdlib-only Python implementing the trust/control layer approved in
Phases 3.3 and 3.3A.
"""

from .enums import (
    SourceType,
    AuthorityLevel,
    CaseScopeValue,
    ScopeProvenance,
    ValidationResult,
    FinalStatus,
    InvestigationState,
)
from .user_context import UserContext
from .evidence import (
    Document,
    ExtractedFact,
    Source,
    Claim,
    Hypothesis,
    SupportingEvidence,
    ContradictoryEvidence,
    Verification,
    MissingEvidence,
    Conflict,
    EvidenceLedger,
)
from .case_scope import (
    CaseScope,
    establish_from_user_selection,
    establish_from_validated_field,
    reject_llm_inference_as_scope,
    resolve_case_scope,
)
from .adjudication import Adjudication, AdjudicationError
from .state_machine import InvestigationStateMachine, IllegalTransitionError
from .investigation import Investigation
from .authority import (
    ClaimType,
    AuthorityResult,
    AuthorityDecision,
    AuthorityEngineError,
    PotentialConflict,
    APPROVED_LICENSE_BASES,
    evaluate_source_authority,
    flag_potential_conflict,
)

__all__ = [
    "SourceType", "AuthorityLevel", "CaseScopeValue", "ScopeProvenance",
    "ValidationResult", "FinalStatus", "InvestigationState",
    "UserContext",
    "Document", "ExtractedFact", "Source", "Claim", "Hypothesis",
    "SupportingEvidence", "ContradictoryEvidence", "Verification",
    "MissingEvidence", "Conflict", "EvidenceLedger",
    "CaseScope", "establish_from_user_selection", "establish_from_validated_field",
    "reject_llm_inference_as_scope", "resolve_case_scope",
    "Adjudication", "AdjudicationError",
    "InvestigationStateMachine", "IllegalTransitionError",
    "Investigation",
    "ClaimType", "AuthorityResult", "AuthorityDecision", "AuthorityEngineError",
    "PotentialConflict", "APPROVED_LICENSE_BASES",
    "evaluate_source_authority", "flag_potential_conflict",
]
