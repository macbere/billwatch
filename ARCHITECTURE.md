# BillWatch Architecture

This reflects the actual implemented architecture as of Build 4F. Nothing below is aspirational -- every box is a real module in this repository.

## Full Pipeline (billwatch/pipeline.py::run_investigation)

    Document(s)
         |
         v
    [Investigation.ledger.add_document()]   -- deterministic, Build 1
         |
         v
    +-----------------------------------------------------------+
    | EXTRACTION                                                 |
    | extraction_integration.py::integrate_extraction()          |
    |   -> LLMProvider.complete_json()          (Gemini, UNTRUSTED)
    |   -> llm_schemas.py::parse_extraction_candidate()  (validates)
    |   -> EvidenceLedger.add_fact()            (deterministic)     |
    +-----------------------------------------------------------+
         |  (fail-closed: any failure stops the pipeline here)
         v
    transition_to(EXTRACTED)
         |
         v
    [Investigation.set_case_scope()]   -- deterministic, never guessed
         |
         v
    transition_to(SCOPED)
         |
         v
    +-----------------------------------------------------------+
    | HYPOTHESIS                                                  |
    | hypothesis_integration.py::generate_and_record_hypothesis() |
    |   -> LLMProvider.complete_json()          (Gemini, UNTRUSTED)
    |   -> llm_schemas.py::parse_hypothesis_candidate() (validates)
    |   -> EvidenceLedger.add_claim() + add_hypothesis()          |
    +-----------------------------------------------------------+
         |  (fail-closed)
         v
    transition_to(HYPOTHESES_GENERATED)
         |
         v
    +-----------------------------------------------------------+
    | VERIFICATION                                                |
    | verification_integration.py::verify_hypothesis()            |
    |   -> LLMProvider.complete_json()          (Gemini, UNTRUSTED)
    |   -> llm_schemas.py::parse_verification_candidate() (validates)
    |   -> reference_data.py  (REAL HCPCS/ICD-10/NCCI lookups)     |
    |   -> authority.py::evaluate_source_authority()  (REAL decision)
    |   -> authority.py::flag_potential_conflict()   (never resolves)
    |   -> EvidenceLedger.add_verification() / add_missing_evidence()
    |      / add_conflict()                                        |
    +-----------------------------------------------------------+
         |  (fail-closed)
         v
    transition_to(EVIDENCE_RETRIEVED) -> transition_to(VERIFIED)
      -> transition_to(CONFLICT_CHECKED) -> transition_to(ADJUDICATED)
         |
         v
    +-----------------------------------------------------------+
    | ADJUDICATION -- ZERO LLM INPUT                              |
    | adjudication_integration.py::adjudicate_investigation()     |
    |   -> compute_final_status()  (pure deterministic Python)    |
    |   -> Investigation.adjudicate()  (records real Adjudication)|
    +-----------------------------------------------------------+
         |
         v
    FinalStatus: SUPPORTED_DISCREPANCY | NO_SUPPORTED_DISCREPANCY
                 | INSUFFICIENT_EVIDENCE | CONFLICTING_EVIDENCE
         |
         | (only if SUPPORTED_DISCREPANCY -- Gate 3 enforced)
         v
    +-----------------------------------------------------------+
    | APPEAL (conditional)                                        |
    | appeal_integration.py::generate_appeal_draft()               |
    |   -> state_machine.py Gate 3 checked FIRST, before any call |
    |   -> LLMProvider.complete_json()          (Gemini, UNTRUSTED)
    |   -> llm_schemas.py::parse_appeal_draft_candidate() (validates)
    |   -> returns transient AppealDraftResult (never persisted)  |
    +-----------------------------------------------------------+

## The Three Hard Gates

1. Scope/Authority Gate -- authority.py, contextual per (source_type, case_scope, claim_type)
2. User-Bias Gate -- evidence.py, UserContext structurally separate from Source/evidence
3. Appeal-Anyway Gate -- state_machine.py, appeal drafting code-gated on final_status == SUPPORTED_DISCREPANCY

## What the Orchestrator Does and Does Not Do

pipeline.py IS: a traffic controller that sequences the five bounded components above and owns the Investigation state-machine transitions between them, fail-closed at every stage.

pipeline.py IS NOT: a sixth reasoning engine. It never calls an LLM directly, never computes FinalStatus itself, and never accepts a caller-supplied final_status -- there is no such parameter anywhere in its function signature.
