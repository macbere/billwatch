"""
Enumerations for the BillWatch Evidence Data Model + State Machine (Build 1).

These enums exist to make illegal values unrepresentable wherever possible --
e.g. a FinalStatus can only ever be one of the four approved values, never an
arbitrary string produced by an LLM.
"""

from enum import Enum


class SourceType(Enum):
    """The 8 evidence source categories from Phase 3.2's corrected hierarchy."""
    PLAN_POLICY = "plan_policy"
    EOB = "eob"
    CMS_MEDICARE = "cms_medicare"
    CMS_NCCI = "cms_ncci"
    CODE_DEFINITION = "code_definition"
    PUBLIC_REGULATORY = "public_regulatory"
    PROVIDER_BILL_LABEL = "provider_bill_label"
    LLM_INTERPRETATION = "llm_interpretation"


class AuthorityLevel(Enum):
    """
    Authority is assigned by deterministic scope-checking code (Gate 1),
    never asserted directly by the source itself or by an LLM.
    """
    CONTROLLING = "controlling"
    CORROBORATING = "corroborating"
    CONTEXTUAL = "contextual"
    REJECTED = "rejected"


class CaseScopeValue(Enum):
    MEDICARE = "medicare"
    MEDICAID = "medicaid"
    PRIVATE_COMMERCIAL = "private_commercial"
    UNKNOWN = "unknown"


class ScopeProvenance(Enum):
    """
    How a CaseScope value was established. Per Phase 3.3A Correction 2,
    only USER_SELECTED and VALIDATED_*_FIELD may ever produce a PASS
    validation_result. LLM_INFERENCE is included explicitly so that any
    attempt to use it is visibly and permanently rejected, not silently
    ignored.
    """
    USER_SELECTED = "user_selected"
    VALIDATED_EOB_FIELD = "validated_eob_field"
    VALIDATED_PLAN_DOCUMENT_FIELD = "validated_plan_document_field"
    LLM_INFERENCE = "llm_inference"
    NONE = "none"


class ValidationResult(Enum):
    PASS = "pass"
    FAIL = "fail"


class FinalStatus(Enum):
    """The only four legal outcomes of an adjudication."""
    SUPPORTED_DISCREPANCY = "supported_discrepancy"
    NO_SUPPORTED_DISCREPANCY = "no_supported_discrepancy"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class InvestigationState(Enum):
    INGESTED = "ingested"
    EXTRACTED = "extracted"
    SCOPED = "scoped"
    HYPOTHESES_GENERATED = "hypotheses_generated"
    EVIDENCE_RETRIEVED = "evidence_retrieved"
    VERIFIED = "verified"
    CONFLICT_CHECKED = "conflict_checked"
    ADJUDICATED = "adjudicated"
