# Project Scope

## Project Name Candidates

- **BillWatch** — confirmed project name.
- BillWatch: Evidence-Grounded Medical-Bill Investigation.
- BillWatch: A Human-Controlled Bill Review Taskmaster.

## One-Line Summary

BillWatch is a fail-closed medical-bill investigation assistant that extracts exact source evidence, pauses for missing context, resumes after human confirmation, checks bounded reference data, and produces an auditable next-action summary without making unsupported claims or sending anything externally.

## Target User

- A person reviewing an itemized medical bill who needs help understanding what can and cannot be supported by the available evidence.
- The user may not know billing terminology and needs plain-language questions, careful uncertainty, and a visible record of how each finding was reached.
- This proof of concept uses only synthetic or appropriately licensed data and is not medical, legal, insurance, or payment advice.

## Problem

Medical-bill review is a multi-step evidence problem. Codes alone do not establish that a charge is incorrect: payer/program, service date, claim relationship, modifiers, reference scope, effective period, verification, and licence basis can all change whether a rule applies. A generic chatbot can easily overstate conclusions or hide missing context. BillWatch needs to show useful autonomous work while pausing instead of guessing and keeping consequential decisions under human control.

## Core Workflow

1. The user pastes an itemized medical bill or loads a supported TXT, CSV, or JSON file.
2. The user may provide payer/program, service date, modifiers, claim/EOB status, and same-date/same-beneficiary-or-claim confirmations.
3. BillWatch validates size and request limits, creates an investigation identifier, and sends the bill through the existing `POST /investigate` path. The server processes the request transiently and does not persist or log raw bill content.
4. The existing analyzer extracts literal codes, dates, and amounts with exact source spans, rejects unsupported model output, deduplicates codes, creates every unique supported pair, and evaluates the pairs against the applicable bounded reference source.
5. The browser records only stages that genuinely occurred and displays a concise evidence-and-investigation timeline.
6. When required context is missing or uncertain, the workflow pauses. The UI explains the missing items and asks the user to correct or confirm only the existing context fields.
7. The user selects **Resume investigation**. BillWatch safely re-runs the existing analysis with the same browser-held bill text and updated context, while the browser retains the earlier attempt and the human decision in the active-tab audit trail.
8. If an extracted code or exact source fact is wrong, the user must edit the original bill text and begin a fresh investigation; the proof of concept does not edit evidence in place.
9. The final report shows bounded status, exact evidence, every pair finding, missing context, reference provenance and licence metadata, stages completed, human decisions, and a safe proposed next step.
10. A simulated consequential-action control demonstrates that approval is required. Approve or reject is recorded only in the browser timeline; even approval sends no appeal, message, payment, document, or external request.

## What We Are Building

### Must ship within the 10-hour budget

1. **Real pause, correct/confirm, and resume loop**
   - Browser-session-only investigation state.
   - Guided prompts for missing existing context fields: payer/program, service date, modifiers, same-date confirmation, same-beneficiary/claim confirmation, and claim status.
   - Resume reuses the existing analyzer rather than replacing it.
   - Progress may be lost when the tab closes; the UI and documentation state this proof-of-concept limitation clearly.

2. **Honest evidence and stage timeline**
   - Show only operations that actually happened in the public analyzer or browser interaction.
   - Candidate events: bill received, facts extracted, code pairs generated, references checked, context evaluated, paused, human context supplied, analysis resumed, final result produced, and approval decision recorded.
   - Preserve exact source spans and bounded result language.

3. **Exactly one isolated synthetic verified rule**
   - Use unmistakably synthetic identifiers such as `BW-DEMO-001` and `BW-DEMO-002` only in a prominently labelled synthetic demo path.
   - Keep the rule in a separate synthetic dataset or module; never mix it with or describe it as the illustrative NCCI fixture.
   - Display author-written source, synthetic version, effective date, retrieval date, verification flag, checksum or equivalent integrity metadata, licence basis, and scope.
   - Its sole purpose is to demonstrate that verified synthetic evidence plus complete context can legitimately reach `POTENTIAL_DISCREPANCY`.
   - Never represent the identifiers or rule as CPT, HCPCS, CMS, AMA, insurer, payer, or clinical data.

4. **Visible, simulated approval boundary**
   - A safe proposed-action card and explicit approve/reject checkpoint.
   - No real appeal drafting or sending, messaging, provider/payer contact, payment behavior, storage, or external integration.
   - The UI must say that approval is simulated and nothing was sent.

5. **Safety and verification work**
   - Inspect and extend existing components; do not rebuild working paths.
   - Preserve POST-only investigation safety, request/rate/pair limits, offline operation, exact source validation, deterministic gates, reference provenance/licence checks, no raw bill logging/storage, and existing result semantics.
   - Add focused tests for pause/resume, browser-session behavior where testable, synthetic-rule isolation, unverified-evidence blocking, timeline truthfulness, and non-sending approval.
   - Run existing regression tests before and after important implementation steps.

### Priority order if time runs short

1. Pause -> human correction or confirmation -> resume.
2. Concise evidence and genuine-stage timeline.
3. Simulated external-action approval gate.

### Suggested 10-hour allocation

- 1 hour: recoverable backup, development-dependency/test preflight, and exact implementation map.
- 3 hours: browser-session investigation model and pause/resume interaction.
- 2 hours: isolated synthetic rule, deterministic gating, metadata, and tests.
- 1.5 hours: evidence/stage timeline and report presentation.
- 0.5 hour: simulated approval boundary.
- 1 hour: regression, browser, privacy, and failure-path verification.
- 1 hour: deployment check, README/demo instructions, and recording rehearsal.

## What We Are Not Building

- Official NCCI acquisition, importing, refresh, or public data distribution.
- Integration of the existing SQLite NCCI repository into the public workflow.
- Use or publication of protected CMS, AMA, payer, insurer, or clinical data without an established licence.
- The full deeper internal pipeline as the public end-to-end workflow.
- Server-side investigation persistence, raw bill storage, databases, user accounts, authentication, cross-device resume, or multi-user sessions.
- PDF/image ingestion, OCR, handwriting recognition, or general document processing beyond the existing TXT, CSV, JSON, and pasted-text path.
- In-place editing of extracted facts or evidence spans.
- Real appeal generation or sending, complaints, messages, emails, documents, payments, provider/payer contact, or other external actions.
- A claim that a bill is fraudulent, illegal, definitely wrong, or guaranteed to contain an error.
- A broad redesign, new frontend framework, unrelated refactoring, or replacement of working analyzer components.
- Production-grade persistence, health-data compliance claims, comprehensive payer coverage, or a production medical-billing product.

## Inspiration And References

- **TurboTax-style guided review:** ask only for missing information, explain why it matters, pause, and resume without making the user understand the underlying rules.
- **GitHub Actions-style run visibility:** show a compact ordered timeline of completed, paused, and resumed stages with inspectable evidence.
- **Stripe-style approval boundaries:** separate automated analysis from decisions that require a person.
- Existing BillWatch design direction: dark navy foundation, restrained blue and teal accents, strong contrast, readable typography, generous spacing, and calm evidence cards.
- Written voice: a calm guide plus neutral investigator; plain language, explicit uncertainty, and no pressure to dispute or withhold payment.

## Demo Path

### Main story: human-controlled agentic investigation

1. Open BillWatch and clearly state that the session exists only in the active browser tab.
2. Load the prominently labelled synthetic `BW-DEMO-001` / `BW-DEMO-002` bill example with required context intentionally missing.
3. Run the investigation and show exact extracted evidence, pair creation, bounded synthetic reference metadata, and the pause.
4. Supply or confirm the missing context and resume without losing the first attempt or audit events.
5. Show the verified synthetic rule reaching `POTENTIAL_DISCREPANCY`, accompanied by careful language that this is a review signal, not proof the bill is wrong.
6. Show the evidence-and-stage timeline, including the human correction/confirmation and resumed analysis.
7. Attempt the proposed external action. Show the explicit approval checkpoint, record an approve or reject choice, and prove that nothing is sent.

### Short safety proofs

- Run an arbitrary medical-bill example whose pairs have no matching rule and show `NO_SUPPORTED_DISCREPANCY_FOUND` without claiming the bill is error-free.
- Run the existing illustrative NCCI example and show `REFERENCE_UNVERIFIED`, proving that unverified evidence cannot produce a potential-discrepancy result.
- Close or reset the tab during rehearsal to confirm and document that browser-session progress is intentionally not durable.

## Definition Of Done

- The main demo completes the real pause/correct-or-confirm/resume loop in one browser tab.
- The timeline matches actual operations and retains both analysis attempts plus the human decision.
- Exactly one isolated author-written synthetic rule can reach `POTENTIAL_DISCREPANCY`; the unverified illustrative NCCI fixture cannot.
- The no-match case remains cautious and does not claim the bill is clean.
- The approval gate is visible, records a local choice, and performs no external action.
- Raw bill content is not logged or persisted on the server; session behavior and limits are documented.
- Existing safety behavior and regression tests remain intact, with new focused tests passing.
- The deployed demo, README, and video description accurately distinguish existing behavior, newly added behavior, synthetic evidence, simulated controls, and out-of-scope production capabilities.

## Constraints And Risks

- The current folder is not recognized as a Git working tree, so a recoverable backup must be established before application-code changes.
- Full unittest discovery currently cannot complete because the Windows environment lacks the `httpx` development dependency. The 30 scope-critical tests pass; dependency/test preflight belongs at the start of implementation.
- The full deeper pipeline and the public analyzer use different workflows. This scope intentionally avoids presenting the internal pipeline as public behavior.
- Synthetic identifiers require a narrow, explicit demo-only recognition path so they cannot be mistaken for real medical billing codes.
- Browser-only state is privacy-preserving and fast to build, but it is not durable and must not be described as production persistence.

## Submission Story

BillWatch demonstrates a Taskmaster that does useful work without pretending autonomy is certainty. It ingests arbitrary supported medical-bill text, grounds facts in exact evidence, checks every code pair against bounded references, stops when context or authority is insufficient, accepts a human correction, and resumes with an auditable history. The central moment is not an accusation—it is the agent choosing to pause, explain what it lacks, and continue only after a person supplies the missing context. A separate synthetic rule proves the complete deterministic path, while the unverified reference case and non-sending approval gate make the safety boundaries visible rather than merely claimed.

This supports the hackathon criteria by emphasizing real operational utility, disciplined trust boundaries and failure handling, and a clear live demonstration with reproducible tests and visible Google Cloud deployment proof.
