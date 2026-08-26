# BillWatch

**All Things Agentic Hackathon — Taskmaster track**

BillWatch is an agentic medical-bill investigator. It runs a guarded, multi-step
investigation pipeline against a bill, and only when the evidence genuinely
supports a discrepancy does it draft an appeal for human review.

**Live demo:** https://billwatch-403260979598.us-central1.run.app

## Problem

Medical billing errors are common, but disputing them today requires either the
patient's own coding/policy literacy or a paid medical billing advocate. Most
patients have neither the time nor the expertise to catch an improperly billed
code pair.

## Solution

BillWatch executes a controlled, multi-step workflow rather than acting as a
conversational chatbot:

    Bill -> Scope -> Evidence -> Verification -> Decision -> Appeal

An LLM (Gemini) may extract facts, propose hypotheses, and propose what to
verify -- but every consequential decision (is a source authoritative, is
evidence sufficient, what is the final status, is an appeal eligible) is made
by deterministic Python code, never the model. The appeal-drafting step is
only reachable after the deterministic pipeline itself reaches a
SUPPORTED_DISCREPANCY state.

## Core Architectural Principle

> LLMs populate structured fields. Deterministic code decides what those fields mean.

Every LLM response is treated as untrusted input. It is parsed by a strict
schema validator that rejects anything malformed, out-of-contract, or
attempting to smuggle a domain decision (final_status, case_scope,
authority_result, appeal_eligible, and related terms) -- the entire candidate
is discarded, not repaired, if this happens anywhere in the response, at any
nesting depth.

## Architecture

See `ARCHITECTURE.md` for the full pipeline diagram and `billwatch-architecture.svg`
for a visual summary. Summary:

    Document(s)
      -> Extraction        (LLM proposes facts; schema validates; recorded in EvidenceLedger)
      -> Case Scope         (deterministic; Medicare/Medicaid/private, never guessed)
      -> Hypothesis          (LLM proposes one candidate explanation; schema validates)
      -> Verification        (LLM proposes source types to check; real deterministic lookups
                               against HCPCS/ICD-10/NCCI-style reference data; real authority decision)
      -> Adjudication         (pure deterministic Python -- computes SUPPORTED_DISCREPANCY /
                               NO_SUPPORTED_DISCREPANCY / INSUFFICIENT_EVIDENCE /
                               CONFLICTING_EVIDENCE from the evidence gathered above)
      -> Appeal (conditional)  (only reachable if SUPPORTED_DISCREPANCY; drafts appeal text
                                citing only real ledger facts/claims; transient, never persisted)

**Web UI:** a stdlib-only Python HTTP server (`app.py`) serves a single-page
embedded HTML/CSS/JS frontend at `/`, and the JSON API at `/health` and
`/investigate`. The frontend calls `/investigate` with a relative fetch, so
it works identically in local development and on Cloud Run.

## Technology Stack

- **Language:** Python 3.14 (stdlib-only for the deterministic core and web server)
- **LLM:** Google Gemini, model `gemini-3.5-flash`, accessed via the official
  `google-genai` SDK (`google-genai==2.17.0`) -- satisfies the hackathon's
  Google Agent Framework requirement
- **Cloud infrastructure:** Google Cloud Run (project `gen-lang-client-0537118940`,
  region `us-central1`)
- **Platform:** developed and tested natively on Android (Termux)

## Gemini's Role

Gemini is used only to populate structured candidate fields at three points:
evidence extraction, hypothesis generation, and verification-source proposals.
It never determines final_status, case_scope, source authority, or appeal
eligibility -- those are computed by deterministic code that has no LLM input
at all.

## Safety Guardrails (the three hard gates)

1. **Scope/Authority Gate** -- authority is contextual per (source_type,
   case_scope, claim_type); CMS/NCCI-style sources are never globally
   authoritative.
2. **User-Bias Gate** -- the user's own stated concern (UserContext) is
   structurally separate from evidence and can never enter the
   reasoning/evidence pipeline.
3. **Appeal-Anyway Gate** -- appeal drafting is code-gated (not prompt-gated)
   on `final_status == SUPPORTED_DISCREPANCY`; no natural-language
   instruction can bypass it.

## Data Sources

The current demo scenario investigates a fixed bill containing CPT/HCPCS
codes `45378` and `45380` billed on the same date of service. Verification
runs against reference coding/billing bundling data (CMS/NCCI-style
Procedure-to-Procedure rules) loaded in-process via
`billwatch/reference_bootstrap.py` and `billwatch/reference_data.py`. The
current product demonstrates this fixed scenario end-to-end; it does not
yet ingest arbitrary uploaded bills.

## Installation

    cd ~/billwatch
    python3 -m pip install google-genai   # only needed for live Gemini calls

No other dependencies -- the deterministic core is Python standard library only.

## Environment Variables

    export GEMINI_API_KEY='your-real-key-here'   # optional -- only for a real Gemini run

Without `GEMINI_API_KEY` set, both `demo.py` and `app.py` fall back to
`MockLLMProvider`, so everything runs fully offline.

## Testing

    cd ~/billwatch
    python3 -m pytest -q

Current result: **400 passed, 1 warning**. All automated tests use
`MockLLMProvider` or an in-process test server -- no real network or API
calls are made by the test suite.

## Running Locally

    cd ~/billwatch
    export GEMINI_API_KEY='your-real-key-here'   # optional
    PORT=8091 python3 app.py

Then open `http://127.0.0.1:8091/` in a browser, or run the CLI demo:

    python3 demo.py

## Deployment

BillWatch is deployed to Google Cloud Run:

    gcloud run deploy billwatch \
      --source . \
      --project=gen-lang-client-0537118940 \
      --region=us-central1 \
      --allow-unauthenticated \
      --set-env-vars="GEMINI_API_KEY=${GEMINI_API_KEY}" \
      --quiet

`GEMINI_API_KEY` is always supplied as a Cloud Run environment variable at
deploy time -- it is never present in source code, Docker image layers, or
git history.

## Live Demo

Open the production URL and click **Run Live Investigation**:

https://billwatch-403260979598.us-central1.run.app

This calls the real, deployed `/investigate` endpoint (the same backend
verified by the automated test suite) and walks through the actual
Scope -> Evidence -> Verification -> Decision -> Appeal pipeline, showing a
live Gemini-drafted appeal when a supported discrepancy is found.
