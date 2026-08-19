# BillWatch

**All Things Agentic Hackathon — Taskmaster track**

BillWatch is an agentic medical-bill investigator. It cross-references a bill against authoritative public reference data and, only when the evidence genuinely supports it, drafts an appeal for human review.

## Problem

Medical billing errors are common, but disputing them today requires either the patient's own coding/policy literacy or a paid medical billing advocate. Most patients have neither.

## Solution

BillWatch runs a structured, deterministic investigation pipeline. An LLM (Gemini) may extract facts, propose hypotheses, and propose what to verify -- but every consequential decision (is a source authoritative, is evidence sufficient, what is the final status, is an appeal eligible) is made by deterministic Python code, never the model.

## Core Architectural Principle

> LLMs populate structured fields. Deterministic code decides what those fields mean.

Every LLM response is treated as untrusted input. It is parsed by a strict schema validator that rejects anything malformed, out-of-contract, or attempting to smuggle a domain decision (final_status, case_scope, authority_result, appeal_eligible, and related terms) -- the entire candidate is discarded, not repaired, if this happens anywhere in the response, at any nesting depth.

## Architecture

See ARCHITECTURE.md for the full pipeline diagram. Summary:

    Document(s)
      -> Extraction        (LLM proposes facts; schema validates; recorded in EvidenceLedger)
      -> Case Scope         (deterministic; Medicare/Medicaid/private, never guessed)
      -> Hypothesis          (LLM proposes one candidate explanation; schema validates)
      -> Verification        (LLM proposes source types to check; REAL deterministic lookups
                               against HCPCS/ICD-10/NCCI reference data; real authority decision)
      -> Adjudication         (pure deterministic Python -- computes SUPPORTED_DISCREPANCY /
                               NO_SUPPORTED_DISCREPANCY / INSUFFICIENT_EVIDENCE /
                               CONFLICTING_EVIDENCE from the evidence gathered above)
      -> Appeal (conditional)  (only reachable if SUPPORTED_DISCREPANCY; drafts appeal text
                                citing only real ledger facts/claims; transient, never persisted)

## Technology Stack

- Language: Python 3.14 (stdlib-only for the deterministic core)
- LLM: Google Gemini, accessed two ways -- a stdlib urllib-based provider and the official google-genai SDK (satisfies the hackathon's Google Agent Framework requirement)
- Platform: developed and tested natively on Android (Termux)

## Gemini's Role

Gemini is used only to populate structured candidate fields at three points: evidence extraction, hypothesis generation, and verification-source proposals. It never determines final_status, case_scope, source authority, or appeal eligibility -- those are computed by deterministic code that has no LLM input at all.

## Safety Guardrails (the three hard gates)

1. Scope/Authority Gate -- authority is contextual per (source_type, case_scope, claim_type); CMS/NCCI is never globally authoritative.
2. User-Bias Gate -- the user's own stated concern (UserContext) is structurally separate from evidence and can never enter the reasoning/evidence pipeline.
3. Appeal-Anyway Gate -- appeal drafting is code-gated (not prompt-gated) on final_status == SUPPORTED_DISCREPANCY; no natural-language instruction can bypass it.

## Installation

    cd ~/billwatch
    python3 -m pip install google-genai   # only needed for live Gemini calls

No other dependencies -- the deterministic core is Python standard library only.

## Testing

    cd ~/billwatch
    python3 -m unittest discover -s tests -v

All automated tests use MockLLMProvider -- no real network or API calls are made by the test suite.

## Running the Demo

    cd ~/billwatch
    export GEMINI_API_KEY='your-real-key-here'   # optional -- only for a real Gemini run
    python3 demo.py

See demo.py for a runnable, end-to-end example: a document containing an NCCI-bundled code pair goes through the full pipeline and (given Medicare scope) produces a SUPPORTED_DISCREPANCY result with a drafted appeal. Without a GEMINI_API_KEY set, the demo runs against MockLLMProvider instead, so it always works offline.
