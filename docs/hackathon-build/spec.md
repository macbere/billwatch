# Technical Spec

## Overview

This spec describes the smallest safe implementation that turns the existing BillWatch public application into the approved hackathon workflow. It extends the working Python application rather than replacing it.

The implementation keeps:

- Python's built-in HTTP server;
- the single `POST /investigate` endpoint;
- the inline HTML, CSS, and JavaScript in `app.py`;
- the existing arbitrary medical-bill analyzer and its deterministic safety gates;
- optional Gemini-assisted extraction with exact source-span validation;
- offline deterministic operation;
- local bounded reference data, request limits, rate limits, POST-only investigation safety, and no raw-bill logging;
- the current Docker and Google Cloud Run deployment shape.

The implementation adds:

- one browser-memory investigation object;
- a real pause, human context confirmation, and fresh-POST resume loop;
- a truthful attempt and stage timeline;
- backward-compatible optional response metadata for completed stages and structured missing context;
- exactly one isolated public synthetic rule for `BW-DEMO-001` / `BW-DEMO-002`;
- a simulated approval decision that changes browser memory only and performs no network or document action;
- focused automated and manual verification.

The deeper internal pipeline, SQLite NCCI repository, and established internal synthetic plan-policy fixture remain disconnected from the public workflow.

## Locked Constraints

- Total implementation, testing, deployment, and rehearsal budget: **10 hours**.
- Do not add Flask, Django, FastAPI, React, Vue, a database, authentication, server sessions, or browser persistence.
- Do not add `localStorage`, `sessionStorage`, IndexedDB, cookies, or another durable client store.
- Refreshing, navigating away from, or closing the tab destroys the active investigation.
- Do not alter the deeper internal pipeline or describe it as the public workflow.
- Do not import, download, bundle, or publish official NCCI, AMA, payer, insurer, or clinical data.
- Do not represent synthetic identifiers as CPT, HCPCS, CMS, AMA, insurer, payer, or clinical data.
- Do not generate or send an appeal, complaint, message, document, payment instruction, provider contact, payer contact, or any other external action.
- Preserve all existing public request limits, exact evidence validation, pair limits, result language, and fail-closed behavior.
- Establish a recoverable file backup before changing application code because this folder is not currently recognized as a Git working tree.

## Stack

### Runtime

- **Python 3.14 container**, preserving the existing `python:3.14-slim` base image.
- **Python standard library `http.server`**, preserving `HTTPServer` and `BaseHTTPRequestHandler`.
- **Python dataclasses and standard library utilities** for immutable result and synthetic-rule records.

### Browser

- Existing inline HTML, CSS, and plain JavaScript in `app.py`.
- Standard browser `fetch()` for `POST /investigate`.
- One plain JavaScript object for active state.
- Native semantic controls, `<details>` for compact prior attempts, and existing focus-visible styling.

### Existing Python dependencies

- `google-genai>=2.17.0` for optional live Gemini extraction.
- `httpx>=0.28.1`, required by the Google Gen AI SDK and the development environment.
- `pytest>=8.0` in development, while retaining the existing `unittest` suite.

### Deployment

- Existing `Dockerfile` and `/health` endpoint.
- Existing Google Cloud Run service and public URL: `https://billwatch-403260979598.us-central1.run.app`.
- The submission must use a newly verified revision of that existing service, not assume the currently deployed revision matches the local files.

### New dependencies

None. Browser automation frameworks, frontend packages, templating engines, databases, and persistence libraries are outside the timebox.

## Architecture

### Component 1: Browser Investigation Coordinator

The inline JavaScript in `app.py` owns the active investigation and presentation. It keeps the raw bill only in page memory, submits every analysis attempt, retains prior responses, records human events, and renders pause, resume, final, failure, and simulated approval states.

It never decides whether evidence supports a discrepancy. It displays the server's deterministic status and structured missing-context metadata.

Implements:

- `prd.md > Epic 1: Understand The Safety And Session Boundary`
- `prd.md > Epic 2: Submit An Arbitrary Supported Medical Bill`
- `prd.md > Epic 5: Follow A Truthful Investigation Timeline`
- `prd.md > Epic 6: Pause For Missing Context`
- `prd.md > Epic 7: Resume After Human Confirmation`
- `prd.md > Epic 8: Receive A Cautious, Auditable Report`
- `prd.md > Epic 9: Demonstrate A Non-Sending Approval Boundary`
- `prd.md > Epic 10: Recover Honestly From Errors Or Reset The Session`

### Component 2: Stateless HTTP Boundary

`app.py` continues to expose:

- `GET /` for the public page;
- `GET /health` for deployment smoke checks;
- `POST /investigate` for all standard and synthetic-demo analysis attempts;
- `GET /investigate` as `405 Method Not Allowed`.

The server validates content length, JSON shape, bill-text limits, payer and context values, rate limits, and the optional demo flag. It does not store an investigation between requests. Resume is a new request using the browser-held source and updated context.

Implements:

- `prd.md > Epic 2`
- `prd.md > Epic 7`
- `prd.md > Epic 10`

### Component 3: Existing Ordinary-Bill Analyzer

`billwatch/arbitrary_analysis.py` remains the ordinary medical-bill truth path. Standard requests continue to use the same code shapes, exact source evidence, unique-pair expansion, reference lookup, payer/date/modifier/claim gates, and bounded statuses.

Only optional, backward-compatible metadata is added:

- completed stage keys;
- structured user-suppliable missing context;
- non-user-suppliable blocking context;
- a `can_resume` indication.

Existing `success`, `status`, `facts`, `findings`, `missing_context`, `review_note`, `failure_reason`, `gemini_mode`, `request_id`, and `limits` semantics remain compatible.

Implements:

- `prd.md > Epic 2`
- `prd.md > Epic 4: See Source-Grounded Evidence And A Real Investigation Plan`
- `prd.md > Epic 6`
- `prd.md > Epic 7`
- `prd.md > Epic 8`

### Component 4: Isolated Public Synthetic Demo

A new `billwatch/synthetic_demo.py` contains exactly one public author-written rule for the unordered pair `BW-DEMO-001` / `BW-DEMO-002`.

This module is invoked only when `app.py` accepts the exact optional flag value `hackathon_synthetic_v1`. When the flag is absent, ordinary analysis follows the existing path and the synthetic module is not consulted. Unknown, boolean, numeric, case-variant, or other flag values are rejected rather than guessed.

The module owns:

- the two unmistakably synthetic identifiers;
- one controlled synthetic sample bill;
- exact identifier scanning and source-span evidence;
- one immutable synthetic pair rule;
- the rule's author-written source label, version, effective date, retrieval date, verification flag, licence basis, scope, and SHA-256 integrity value;
- deterministic context and effective-period gates;
- synthetic pair findings in the existing public result shape.

The public rule is not inserted into `ReferenceStore`, `ncci_ptp`, or the deeper plan-policy dataset. The established deeper synthetic plan-policy fixture remains untouched and unexposed.

Implements:

- `prd.md > Epic 3: Keep The Synthetic Demonstration Separate`
- `prd.md > Epic 4`
- `prd.md > Epic 6`
- `prd.md > Epic 8`
- `prd.md > Epic 9`

### Component 5: Existing Reference Boundary

`billwatch/reference_bootstrap.py` and `billwatch/reference_data.py` continue to provide ordinary bounded reference behavior. The illustrative NCCI relationship remains unverified. It must continue to produce a pair-level `REFERENCE_UNVERIFIED` outcome and must never produce `POTENTIAL_DISCREPANCY` or the simulated approval card.

No public path is added to the NCCI importer, SQLite repository, or protected reference acquisition.

Implements:

- `prd.md > Epic 4`
- `prd.md > Epic 8`

### Component 6: Optional Gemini Extraction Boundary

`app.py` keeps the existing provider selection:

- when `GEMINI_API_KEY` exists, `GenAISDKProvider` may propose literal extracted facts;
- otherwise, `InputDrivenMockProvider` performs deterministic input-driven extraction.

Gemini never decides reference applicability, missing context, status, stage completion, or approval availability. Existing schema validation and exact source-span checks remain mandatory.

The synthetic demo path is deterministic and does not depend on Gemini interpreting the synthetic identifiers. This makes the central demonstration reliable and prevents synthetic labels from being treated as medical-code knowledge.

Implements:

- `prd.md > Epic 4.1: Inspect extracted facts`
- `prd.md > Epic 8`

### Component 7: Cloud Run Container

The existing container continues to listen on `0.0.0.0` using the injected `PORT` value. Deployment creates a new revision of the existing Cloud Run service only after local regression and browser verification pass.

No server persistence service, database, volume, or background worker is added.

Implements:

- the deployed proof required by `prd.md > Submission Proof Points`;
- the session and failure boundaries in `prd.md > Epics 1 and 10`.

## PRD Traceability Summary

| PRD epic | Primary implementation owner | Verification focus |
| --- | --- | --- |
| 1. Safety and session boundary | `app.py` UI and page-memory state | Notice visible; no browser/server persistence |
| 2. Arbitrary bill submission | Existing form, `/investigate`, ordinary analyzer | Paste/TXT/CSV/JSON, limits, POST-only behavior |
| 3. Synthetic demonstration | `billwatch/synthetic_demo.py`, explicit UI card | Exactly one public rule; ordinary path isolation |
| 4. Evidence and plan | Existing extraction/analyzer and reference metadata | Exact spans, all pairs, provenance and scope |
| 5. Truthful timeline | Browser investigation object plus server stage metadata | Only returned/completed stages; attempts retained |
| 6. Missing-context pause | Structured missing-context response plus pause renderer | Only user-suppliable fields; source locked |
| 7. Resume | Browser coordinator and fresh `/investigate` POST | Human event, new request, prior attempt retained |
| 8. Auditable report | Existing result shape plus careful renderer | Bounded language and every pair visible |
| 9. Simulated approval | Browser-only event handler | Only after potential discrepancy; zero network action |
| 10. Errors and reset | Client validation, retry, confirmation, API errors | No invented stages; input retained; reset confirmed |

## File Structure

```text
billwatch-system/
├── app.py
│   Existing HTTP server and inline HTML/CSS/JavaScript.
│   Extend with the Hackathon Demo card, page-memory investigation object,
│   pause/resume/timeline renderers, strict demo-flag routing, and simulated approval.
├── billwatch/
│   ├── arbitrary_analysis.py
│   │   Preserve ordinary analysis; add backward-compatible completed-stage and
│   │   structured-missing-context metadata.
│   ├── synthetic_demo.py                 [new]
│   │   Exactly one public synthetic pair rule, exact evidence scanner,
│   │   provenance/checksum metadata, gates, and deterministic result builder.
│   ├── reference_bootstrap.py            [unchanged]
│   │   Existing illustrative datasets and deeper internal plan-policy fixture.
│   ├── reference_data.py                 [unchanged unless a verified blocker appears]
│   │   Existing versioned, fail-closed ordinary reference store.
│   ├── genai_sdk_provider.py             [unchanged]
│   │   Optional Gemini extraction provider.
│   ├── extraction.py                     [unchanged]
│   │   Existing extraction and source-evidence validation.
│   ├── pipeline.py                       [unchanged and not publicly connected]
│   ├── investigation.py                  [unchanged and not publicly connected]
│   └── state_machine.py                  [unchanged and not publicly connected]
├── tests/
│   ├── test_synthetic_demo.py            [new]
│   │   Synthetic metadata, exact evidence, deterministic gates, and isolation.
│   ├── test_arbitrary_analysis.py        [extend]
│   │   Ordinary regression, completed stages, structured missing context,
│   │   unverified evidence, and fail-closed behavior.
│   ├── test_app_routes.py                [extend]
│   │   Backward-compatible HTTP contract, strict demo flag, errors, and limits.
│   ├── test_app_ui_interactions.py       [extend]
│   │   Static UI/state contracts, pause/resume hooks, no persistence APIs,
│   │   and approval handler with no request path.
│   └── existing tests                    [preserve]
├── requirements.txt                     [no new dependency expected]
├── requirements-dev.txt                 [install before the full baseline]
├── Dockerfile                           [preserve unless deployment verification finds a blocker]
├── README.md                             [update]
│   Session loss, synthetic demo boundary, no external action, test evidence,
│   Cloud Run revision, and demo instructions.
└── docs/hackathon-build/
    ├── scope.md
    ├── prd.md
    ├── spec.md
    └── build-notes.md
```

## `POST /investigate` Contract

### Existing request fields

These remain unchanged:

```json
{
  "bill_text": "Itemized bill text",
  "payer_scope": "unknown",
  "service_date": null,
  "modifiers": "",
  "same_date_confirmed": null,
  "same_beneficiary_confirmed": null,
  "claim_status": null
}
```

### Optional synthetic-demo request field

The Hackathon Demo card adds exactly one optional field:

```json
{
  "demo_mode": "hackathon_synthetic_v1"
}
```

Rules:

- Absence means ordinary analysis.
- The only accepted non-empty value is the exact string `hackathon_synthetic_v1`.
- The ordinary form must not send the field.
- The demo flag does not weaken bill-size, request-size, rate, or content-type limits.
- The synthetic analyzer accepts only exact `BW-DEMO-001` / `BW-DEMO-002` identifiers in this mode.
- Unknown values return `400 invalid_request`; they do not fall back to either path.

### Existing response fields

Preserve the current fields and meanings:

```text
success
status
document_id
facts
findings
missing_context
review_note
failure_reason
gemini_mode
request_id
limits
```

### Backward-compatible optional response fields

Add:

```json
{
  "analysis_mode": "standard",
  "completed_stages": [
    "bill_received",
    "facts_extracted",
    "pairs_generated",
    "references_checked",
    "context_evaluated"
  ],
  "missing_context_fields": [
    {
      "field": "service_date",
      "label": "Service date",
      "reason": "The reference must be effective on the service date."
    }
  ],
  "blocking_context": [],
  "can_resume": true
}
```

Rules:

- `analysis_mode` is `standard` or `hackathon_synthetic_v1`.
- Existing clients may ignore every new field.
- `completed_stages` is ordered and created by the analysis path as work completes; it is never a static success list.
- Invalid input produces no investigation result and no completed-stage list.
- A failed analysis may return only stages that actually completed before failure.
- `missing_context_fields` contains only supported fields the user can supply on Resume: `payer_scope`, `service_date`, `modifiers`, `same_date_confirmed`, `same_beneficiary_confirmed`, or `claim_status`.
- `blocking_context` contains evidence limitations that ordinary user context cannot repair, such as an unverified reference or unavailable payer-specific source.
- `can_resume` is true only when at least one structured user-suppliable field can materially advance the analysis.
- Existing string `missing_context` values remain for backward compatibility.
- Raw bill text is never added to a response.

### Status compatibility

- Preserve existing top-level `status` precedence and existing pair-level status semantics.
- Ordinary requests with the bundled unverified NCCI fixture remain unable to reach `POTENTIAL_DISCREPANCY`.
- The UI may emphasize a pair-level `REFERENCE_UNVERIFIED` finding while retaining the safe existing overall status.
- Only the explicitly synthetic rule may reach `POTENTIAL_DISCREPANCY` with checked-in public data.

## Synthetic Rule Contract

The new module defines one immutable rule with values equivalent to:

```text
dataset: billwatch_hackathon_demo
code_a: BW-DEMO-001
code_b: BW-DEMO-002
relationship: author_written_synthetic_pair_review_signal
source: BillWatch Hackathon Demo — author-written synthetic rule
version: bw-hackathon-demo-v1
effective_date: fixed date recorded in the fixture
retrieval_date: fixture authoring date
relationship_verified: true (verified only as author-written synthetic content)
license_basis: author_written_synthetic_demo
scope: billwatch_hackathon_demo_only
source_sha256: SHA-256 of a canonical representation of the rule
```

Required gates for `POTENTIAL_DISCREPANCY`:

1. The exact demo flag was accepted.
2. Both exact identifiers occur in the submitted synthetic source and have exact source spans.
3. The unordered pair matches the one rule.
4. The rule metadata is complete and its integrity value matches the canonical rule content.
5. The supplied service date falls within the rule's explicit effective period.
6. Same-date confirmation is true.
7. Same-beneficiary-or-claim confirmation is true.
8. No deterministic validation failure exists.

The rule is explicitly not payer data. Its displayed scope is “BillWatch Hackathon Demo only,” not Medicare, Medicaid, private/commercial, CMS, AMA, or insurer scope. Only the context applicable to this author-written rule is gated.

If a required user-suppliable field is absent, return `INSUFFICIENT_CONTEXT`, structured fields, `can_resume: true`, exact evidence, and the genuinely completed stages. If the identifier pair does not match, return a cautious no-match/insufficient result without an approval card.

## Browser Memory Model

The page defines one variable, conceptually:

```text
investigation = null

investigation = {
  id,                  first successful request_id
  mode,                standard or hackathon_synthetic_v1
  billText,            raw text held only in page memory
  initialContext,
  currentContext,
  attempts: [],        immutable snapshots of request context and response/error
  timeline: [],        ordered automatic and human events
  state,               running | paused | completed | failed
  approvalDecision     null | approved | rejected
}
```

Implementation rules:

- Do not serialize this object to any storage API.
- Do not place bill text in the URL, DOM attributes, logs, or response metadata.
- The first successful response's `request_id` becomes the display investigation ID.
- Every later response retains its own `request_id` as the attempt ID.
- Keep prior attempt objects append-only while the page is open.
- After pause, disable the original bill-text and file controls.
- Context controls remain available only where the response identifies a user-suppliable missing field.
- Resume appends a human-confirmation event before making a fresh POST.
- The newest successful response is primary; earlier attempts render under `<details>`.
- Start New Investigation or Load Hackathon Demo asks for confirmation when an investigation exists. Cancel changes nothing; confirm sets the object to `null` and clears the UI.
- Refresh and tab close naturally destroy the object. No unload handler attempts to persist or send it.

## End-To-End Data Flow

### Standard first attempt

1. User pastes text or loads TXT/CSV/JSON in the browser.
2. Browser performs existing empty/file/size checks.
3. Browser creates a provisional in-memory attempt and sends the existing context fields to `POST /investigate`; `demo_mode` is absent.
4. Server validates request length, JSON, bill text, limits, context, and rate limit.
5. Server runs the existing provider/extraction/analyzer/reference path.
6. Analyzer records each stage only after it completes.
7. Server returns the existing result plus optional stage and structured-context fields; it does not return raw bill text.
8. Browser creates the investigation ID from the first successful `request_id`, stores the response as attempt 1, and renders evidence, findings, metadata, and timeline.
9. If `can_resume` is false, render the bounded final or blocked result. Approval remains hidden unless top-level status is `POTENTIAL_DISCREPANCY`.

### Synthetic missing-context pause

1. User deliberately chooses the separate Hackathon Demo card.
2. If another investigation exists, browser asks for confirmation before clearing it.
3. Browser loads the clearly labelled synthetic source and records mode `hackathon_synthetic_v1` in memory.
4. Submit includes the exact `demo_mode` value and intentionally incomplete existing context.
5. Server strictly validates the flag and routes only this request to `synthetic_demo.py`.
6. Synthetic module extracts exact identifier evidence, generates the one pair, checks the one rule and metadata, and identifies missing user context.
7. Response contains `INSUFFICIENT_CONTEXT`, exact evidence, the synthetic reference card, genuine completed stages, structured missing fields, and `can_resume: true`.
8. Browser stores attempt 1, renders it, locks original bill text, shows only relevant context controls, and displays **Resume investigation**.

### Resume

1. User supplies or confirms the requested existing context.
2. Browser validates the relevant controls.
3. Browser appends a human event describing only the fields confirmed; it does not rewrite attempt 1.
4. Browser sends a new `POST /investigate` containing the same in-memory bill text, updated context, and the same demo flag where applicable.
5. Server repeats the complete deterministic analysis without relying on a server session or prior response.
6. Browser appends attempt 2 and its actual completed stages.
7. Attempt 2 becomes primary; attempt 1 remains expandable.
8. If all synthetic gates pass, render `POTENTIAL_DISCREPANCY` with cautious language and reveal the simulated approval card.

### Simulated approval

1. Approval card is rendered only when the newest result has top-level `POTENTIAL_DISCREPANCY`.
2. Approve or Reject is a `type="button"` browser event.
3. The handler sets `approvalDecision`, appends a human timeline event, and rerenders the card.
4. The handler performs no `fetch`, navigation, form submission, clipboard action, download, file creation, or external integration.
5. UI states “Nothing was sent.”

The new approval path must not use the existing Copy/Download summary handlers. In synthetic demo mode, those actions are not rendered.

### Retry after failure

1. Client-validation errors create no investigation.
2. After a valid submission, network, 429, 500, malformed response, or analysis failure stores a failed attempt without inventing completed stages.
3. Browser retains bill text and context in memory and shows Retry.
4. Retry performs a fresh POST with the same current input.
5. The failed attempt remains in the active timeline; success is a new attempt.

## Failure Strategy

### Client validation failure

- Examples: empty text, unsupported file type, client-side file-size limit.
- Behavior: show an inline correction message; no request, result, investigation ID, attempt, or timeline is created.

### Invalid API request

- Examples: malformed JSON, missing text, invalid payer value, invalid date, invalid demo flag.
- Behavior: HTTP 400 with existing safe error shape; retain browser input; show correction; do not claim analysis stages completed.

### Request and rate limits

- Preserve HTTP 413 for oversized request and 429 for rate limit.
- Display the server message and Retry only when retrying can reasonably help.
- Never convert a limit response into `NO_MATCHING_RULE` or a bill finding.

### Extraction or provider failure

- Return `success: false` and only stages genuinely completed before the failure.
- Do not show a final bill status or approval.
- Retain input and offer Retry.
- Do not silently substitute a live Gemini failure with a different conclusion.

### Reference failure

- Unverified, unlicensed, out-of-period, absent payer-specific, or inapplicable evidence is a successful fail-closed investigation result, not a network failure.
- Put non-user-fixable limitations in `blocking_context`.
- Keep `can_resume` false when ordinary context cannot resolve the limitation.
- Never show the simulated approval card.

### Browser state loss

- Refresh, navigation, crash, or tab close loses the active investigation by design.
- The first screen and README disclose this limitation.
- No recovery claim or server-history UI is shown.

### Cloud Run failure

- Do not replace a verified working revision until the new revision passes deployment health and browser smoke checks where revision/traffic controls permit.
- If deployment fails, retain the local verified build and record the failure; do not claim the public URL is updated.

## AI And Deterministic Decision Boundary

### Gemini may

- propose literal codes, dates, amounts, and other supported facts from ordinary submitted text;
- return structured extraction proposals through the existing provider boundary.

### Gemini may not

- establish source evidence without an exact matching source span;
- invent a code not present in its cited span;
- determine payer/program applicability;
- decide that services share a date, beneficiary, or claim;
- decide modifier effect, reference verification, effective period, licence, checksum, or scope;
- assign `POTENTIAL_DISCREPANCY`;
- decide completed stages;
- create a human confirmation;
- reveal or approve an external action.

### Deterministic code controls

- input and pair limits;
- exact source-evidence acceptance;
- code deduplication and all unique pair generation;
- ordinary versus synthetic routing;
- synthetic identifier isolation;
- bounded reference lookup and metadata;
- missing-context classification;
- result status;
- stage truthfulness;
- simulated approval visibility.

The central synthetic demo is deterministic and usable with no Gemini key. This is an explicit reliability and safety choice, not a claim that Gemini performed the demo investigation.

## Privacy And Security Controls

- Preserve `Cache-Control: no-store` on HTML and JSON.
- Preserve content-type, frame, referrer, and content security headers.
- Preserve POST-only investigation behavior.
- Preserve server `log_message` suppression so raw bill text and request headers are not logged by application code.
- Do not log request bodies, browser investigation objects, extracted facts, approval choices, or context.
- Do not echo raw bill text.
- Do not add analytics, telemetry, third-party scripts, remote fonts, or external frontend assets.
- Do not use bill content in exception messages returned to the browser.
- If live Gemini is deployed, keep `GEMINI_API_KEY` in Google Secret Manager rather than source code, the Dockerfile, or a plaintext deployment command.
- Do not claim that this proof of concept is production-compliant for protected health information.

## Test Plan

### Phase 0: Backup and baseline

Before application changes:

1. Resolve the intended project folder and create a dated recoverable copy outside the files being edited, because Git is unavailable in this folder.
2. Install or restore `requirements-dev.txt` so `httpx` and the full test loader are available.
3. Run:

   ```text
   python -m unittest discover -s tests -p "test*.py"
   python -m pytest -q
   ```

4. Record exact counts and any pre-existing failures before editing.
5. Re-run the known scope-critical suites before the first change:

   ```text
   python -m unittest tests.test_arbitrary_analysis tests.test_app_routes tests.test_state_machine
   ```

No build task proceeds past an unexplained new baseline regression.

### Synthetic module tests

Create `tests/test_synthetic_demo.py` to prove:

- exactly one public synthetic rule exists;
- the two identifiers and every label are unmistakably synthetic;
- rule metadata is complete and deterministic;
- the recorded checksum matches canonical rule content;
- ordinary medical-code shapes are not reinterpreted as demo identifiers;
- the exact demo flag is required;
- absent, invalid, or case-variant flags cannot access the module through the public route;
- both identifiers must occur in exact cited spans;
- missing date/same-date/same-claim context pauses;
- effective-period failure fails closed;
- all gates are required for `POTENTIAL_DISCREPANCY`;
- the internal plan-policy fixture is unchanged and not exposed by this module.

### Ordinary analyzer regression tests

Extend `tests/test_arbitrary_analysis.py` to prove:

- existing arbitrary medical bills return the same facts, pair count, pair statuses, and overall status when no demo flag is used;
- three unique codes still produce three unique pairs;
- the unverified NCCI record still returns pair-level `REFERENCE_UNVERIFIED` and no review note capable of triggering approval;
- payer/date/modifier/same-date/same-beneficiary gates still fail closed;
- completed stages are ordered and honest;
- zero-pair and extraction-failure paths do not claim reference checks that did not happen;
- structured user fields never misclassify an unverified reference or unavailable payer-specific source as user-correctable;
- request and pair limits remain unchanged.

### HTTP contract tests

Extend `tests/test_app_routes.py` to prove:

- `GET /investigate` remains rejected;
- ordinary requests remain compatible without new fields;
- the exact demo flag reaches the synthetic branch;
- invalid demo flag values return 400;
- the response retains all existing fields;
- optional stage/context fields contain no raw bill text;
- each POST receives a new request ID;
- two direct POSTs with updated context produce two independently evaluated attempts;
- 400, 413, 429, and 500 paths remain safe;
- `/health` remains available and reveals no secret.

### Static UI contract tests

Extend `tests/test_app_ui_interactions.py` to prove the served page contains:

- the browser-session notice;
- the separate, explicit Hackathon Demo card and synthetic labels;
- one in-memory investigation object;
- no `localStorage`, `sessionStorage`, IndexedDB, cookie, beacon, unload-send, or persistence call;
- pause, Resume, Retry, Start New, timeline, and approval controls;
- a Resume code path that invokes the shared fresh-POST function rather than reusing a cached result;
- append-only attempts rather than replacement of the prior attempt;
- an approval handler that mutates browser state and does not call the request function;
- approval buttons with `type="button"`;
- no synthetic approval card in the initial static page state;
- no inline `onclick` handlers.

Static inspection cannot fully prove browser execution. The following manual checks are mandatory rather than adding a new browser framework.

### Manual browser verification

Using local offline mode:

1. Ordinary pasted medical bill and TXT/CSV/JSON loading still work.
2. Empty, invalid, oversized, and unsupported input shows correction without a result.
3. Synthetic demo pauses with exact evidence still visible and bill text locked.
4. Browser Network panel shows one initial POST and one new POST on Resume.
5. The first attempt remains expandable after the second succeeds.
6. Only the returned genuinely completed stages appear.
7. A forced failed request retains input, shows Retry, and marks no false completion.
8. Unverified NCCI evidence shows no simulated approval.
9. No-match result avoids clean-bill language and shows no approval.
10. Synthetic fully gated result shows the approval card.
11. Approve and Reject produce no new Network-panel request, download, navigation, or clipboard action and display “Nothing was sent.”
12. Start New and Load Demo require confirmation before clearing active state.
13. Refresh clears the investigation.
14. Keyboard focus, mobile width, contrast, and expandable history remain usable.

#### Local verification evidence — 2026-08-30

1. **Ordinary input and supported files passed.** A pasted `99213` / `93000` bill produced exact code and amount evidence. Browser-loaded TXT, CSV, and JSON fixtures all populated the ordinary bill field without creating an investigation prematurely.
2. **Invalid-input gates passed.** Empty input showed the browser's required-field correction. A 100,001-character paste, unsupported `.md` file, and 200,001-byte `.txt` file each showed a specific correction with the result hidden and zero timeline entries.
3. **Synthetic pause passed.** Attempt 1 returned `INSUFFICIENT_CONTEXT`, kept exact `BW-DEMO-001` and `BW-DEMO-002` source spans visible, disabled bill/file inputs, and exposed only service-date, same-date, and same-beneficiary/claim controls.
4. **Fresh-POST Resume passed.** The initial request ID was `dcc6ae6c-6ec4-4935-ad34-c16941b098f7`; Resume returned `eb21c9dc-e772-4527-8824-bbe215e8fd27`. The distinct IDs and two attempt entries prove one initial evaluation and one new Resume evaluation.
5. **Earlier attempt retention passed.** `Attempt 1 · INSUFFICIENT CONTEXT` remained in an expandable `<details>` element; opening it showed its original request ID and all three original pause reasons.
6. **Truthful stages passed.** Each synthetic attempt showed only the five returned completed stages—bill received, evidence extraction, pair generation, reference check, and context evaluation—plus real pause/resume/final browser events.
7. **Failure and Retry passed.** With the local server intentionally unavailable, BillWatch retained the bill, showed Retry, recorded no completed stage, and kept `Attempt 1 · DID NOT FINISH` with `Failed to fetch`. Restoring the server and choosing Retry created a separate successful attempt.
8. **Unverified evidence gate passed.** Ordinary `45378` / `45380` analysis displayed `REFERENCE UNVERIFIED`, the illustrative `2026-Q2` record with verification `false`, and no approval card.
9. **No-match caution passed.** Ordinary `99213` / `93000` analysis displayed `NO MATCHING RULE`, explicitly said this does not prove the bill is error-free, and showed no approval card.
10. **Fully gated synthetic result passed.** Human-confirmed context resumed to bounded `POTENTIAL_DISCREPANCY`, displayed `billwatch_hackathon_demo / bw-hackathon-demo-v1`, effective `2026-01-01`, verification `true`, and showed the simulated approval card.
11. **Zero-effect approval passed.** Approve and Reject were tested in separate investigations. Each kept the URL, request ID, report, and attempt count unchanged; raised no download event; exposed no synthetic copy/download action; added one human timeline event; and displayed `Nothing was sent.` Source inspection also confirmed the handler has no request, clipboard, navigation, file, or object-URL call.
12. **Reset confirmation passed.** Both Start New and Load Demo use the shared `confirmClearInvestigation()` guard. An active-state browser check produced a real blocking confirmation before Start New could clear the report; Load Demo likewise cleared active state only after confirmation was accepted. Static UI tests cover the shared guard and cancel-preserves-state branch.
13. **Refresh clearing passed.** Before refresh the paused investigation had 7 timeline events and 245 source characters; afterward the result and approval cards were hidden, the bill was empty, and the timeline had zero entries.
14. **Responsive/accessibility checks passed.** At a 375-pixel client width, document width also remained 375 pixels with no horizontal overflow and all three pause controls readable. Buttons are semantic focusable controls, `:focus-visible` uses a 2-pixel teal outline, and expandable history opened successfully. Contrast ratios were 16.47:1 for primary text, 7.07:1 for muted panel text, 8.87:1 for the focus color, and 4.78:1 for white primary-button text after the scoped accent adjustment.

### Full regression and final evidence

- Run the complete `unittest` and `pytest` suites after each risk-bearing slice and at final local completion.
- Compare final counts with the recorded baseline.
- Record focused test commands and results in `build-notes.md` and README.
- Do not describe a partial loader run as a full passing suite.

## External APIs And Dependency Documentation

No new external API is introduced. These links document only the existing stack and approved deployment path:

- [Python `http.server`](https://docs.python.org/3/library/http.server.html)
- [Python `unittest`](https://docs.python.org/3/library/unittest.html)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)
- [HTTPX documentation](https://www.python-httpx.org/)
- [pytest documentation](https://docs.pytest.org/en/stable/)
- [Browser Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)
- [Dockerfile reference](https://docs.docker.com/reference/dockerfile/)
- [Cloud Run container runtime contract](https://cloud.google.com/run/docs/container-contract)
- [Deploy container images to Cloud Run](https://cloud.google.com/run/docs/deploying)
- [Cloud Run service secret configuration](https://cloud.google.com/run/docs/configuring/services/secrets)

Implementation should use the currently installed dependency versions that pass the baseline. Do not upgrade dependencies merely because newer versions exist during the ten-hour build.

## Cloud Run Deployment And Verification

### Pre-deployment gate

- Full local regression passes.
- Manual browser checklist passes in deterministic offline mode.
- Container builds and starts locally on the expected `PORT` where local Docker is available.
- `/health`, `/`, standard POST, demo pause, demo resume, unverified result, and no-match result work locally.
- README accurately distinguishes offline, optional Gemini, synthetic evidence, and simulated approval.

### Deployment procedure boundary

The checklist must first resolve the actual Google Cloud project, region, service name, current revision, and permissions with read-only commands. Do not infer them solely from the URL and do not create a second service when updating the existing service is intended.

Then:

1. Build from the verified source/Dockerfile using the existing service's established deployment method.
2. Create a new Cloud Run revision.
3. Preserve public-access and environment settings unless an explicit, verified change is required.
4. Keep the central demo functional without `GEMINI_API_KEY`.
5. If live Gemini is enabled, attach the key through Secret Manager and verify that it is not present in source, image history, or plaintext notes.
6. Record the deployed revision identifier and resulting URL.

### Public smoke checks

Against the deployed URL:

- `GET /health` returns 200 and the expected safe mode.
- `GET /` returns the updated UI and browser-session notice.
- `GET /investigate` remains 405.
- Standard arbitrary no-match request remains cautious.
- Existing illustrative NCCI request remains unverified and blocked.
- Synthetic demo completes pause -> human confirmation -> fresh POST -> potential discrepancy.
- Approval records a local decision and causes no network action.
- Refresh clears the timeline.
- No raw bill content appears in application responses beyond the exact evidence fields already required for the report, deployment output, or app logs.

Only after these checks pass may the README and submission describe the public URL as updated.

## Risks And Mitigations

### No working Git backup in the current folder

Risk: application changes may be hard to recover.

Mitigation: first checklist task creates and verifies a dated file backup before any code edit. Do not use destructive Git commands.

### Development dependency missing

Risk: the previously attempted full suite stopped at a missing `httpx` import.

Mitigation: restore `requirements-dev.txt` dependencies and record a complete pre-change baseline before implementation.

### Synthetic path leaks into ordinary analysis

Risk: fake identifiers could be mistaken for medical codes.

Mitigation: exact flag validation, separate module, ordinary-regex preservation, no shared NCCI store, isolation tests, and prominent UI/reference labels.

### Static stages overstate work

Risk: the existing fixed four-stage list can claim success after failure.

Mitigation: remove the static success assumption and render only ordered stage keys returned after actual completion.

### Browser-only logic is difficult to automate without new tooling

Risk: static tests cannot prove every DOM and Network-panel behavior.

Mitigation: keep JavaScript helpers small and inspectable, add static contract tests, use server route tests for every deterministic decision, and require a documented manual browser/network checklist. Do not add Playwright or another framework inside the timebox.

### Inline `app.py` becomes crowded

Risk: pause/resume additions can make one file difficult to review.

Mitigation: preserve the approved file shape but organize JavaScript into short named helpers for payload creation, request execution, state transition, timeline append, and rendering. Avoid unrelated CSS or server refactoring.

### Optional Gemini causes demo instability

Risk: network, credentials, quota, or model response can fail during judging.

Mitigation: central synthetic demo is deterministic; ordinary offline mode remains complete; Gemini remains optional and visibly labelled.

### Cloud Run revision differs from local behavior

Risk: the documented URL may still serve an older revision.

Mitigation: record revision identity and run all public smoke checks after deployment before submission claims.

## Implementation Sequence For Checklist

This section is the direct handoff target for `$build-checklist`.

### Slice 0 — Safety backup and complete baseline (1 hour)

- Verify workspace and create recoverable backup.
- Restore development dependencies.
- Run and record full and focused baseline tests.
- Stop if new unexplained baseline failures exist.

### Slice 1 — Isolated synthetic rule and deterministic tests (1.5 hours)

- Add `billwatch/synthetic_demo.py`.
- Add checksum/provenance/isolation/gate tests.
- Do not touch UI until the module passes focused tests.

### Slice 2 — Backward-compatible response metadata (1 hour)

- Add completed-stage recording and structured missing-context classification.
- Preserve existing fields and ordinary result semantics.
- Extend analyzer and HTTP tests.

### Slice 3 — Browser investigation state and pause/resume (2.5 hours)

- Add page-memory object and session notice.
- Add separate demo card.
- Add shared request helper, pause renderer, source lock, context controls, fresh-POST Resume, attempt retention, reset confirmation, and Retry.
- Verify main demo path manually before polish.

### Slice 4 — Truthful timeline and simulated approval (1 hour)

- Render server-completed stages and browser human events.
- Add compact prior-attempt detail.
- Add approval card only after potential discrepancy.
- Prove approval performs no network/document action.

### Slice 5 — Regression, privacy, and browser verification (1 hour)

- Run complete automated suites.
- Perform failure, no-match, unverified, refresh, mobile, and keyboard checks.
- Inspect source for persistence/logging/external-action regressions.

### Slice 6 — Cloud Run update and public smoke tests (1 hour)

- Resolve existing service configuration.
- Deploy verified revision.
- Run public health, ordinary, synthetic, unverified, approval, and refresh checks.

### Slice 7 — README, evidence, and demo rehearsal (1 hour)

- Update limitations, synthetic labels, AI boundary, test counts, revision evidence, and demo steps.
- Rehearse the pause/resume story and short safety proofs.

Total planned time: **10 hours**. If time is lost, protect Slice 3 first, then the truthful timeline, then the simulated approval presentation. Do not trade away regression, privacy, or unverified-evidence blocking to add polish.

## Demo And Submission Flow

### Main demonstration

1. Open the updated Cloud Run URL and point out the active-tab-only privacy notice.
2. Load the separate Hackathon Demo card and read its synthetic-data warning.
3. Submit the synthetic bill with required context intentionally absent.
4. Show exact spans, the one synthetic pair, provenance/checksum metadata, completed stages, and the pause.
5. Confirm requested context and select **Resume investigation**.
6. Show the new POST, human event, retained first attempt, and newest primary report.
7. Explain that `POTENTIAL_DISCREPANCY` is a review signal, not proof of an incorrect bill.
8. Approve or Reject the simulated action and show “Nothing was sent” plus no new network request.

### Short safety proofs

- Ordinary arbitrary bill: show all unique pairs and a cautious no-match/no-supported-discrepancy result.
- Illustrative NCCI pair: show `REFERENCE_UNVERIFIED` and no approval card.
- Refresh: show that active progress disappears as disclosed.
- Test evidence: show passing focused and full regression commands.
- Deployment evidence: show the verified Cloud Run revision and live URL.

### Claims permitted in submission

- BillWatch performs bounded evidence-grounded investigation of arbitrary supported medical-bill text.
- It pauses for user-suppliable context and resumes with a browser-local audit trail.
- Its public synthetic rule is author-written, isolated, and explicitly not official billing data.
- Unverified evidence cannot produce the synthetic potential-discrepancy path.
- Approval is simulated and sends nothing.

### Claims prohibited in submission

- The deeper internal pipeline is the live public workflow.
- The app imports or verifies current official NCCI data.
- The synthetic rule is medical, payer, CMS, AMA, insurer, or clinical evidence.
- The app proves a bill is wrong, fraudulent, illegal, or guaranteed to contain an error.
- The app sends appeals or other external actions.
- Browser progress is durable or production-grade.
- The proof of concept is a production compliance solution.

## Spec Completion Criteria

The technical plan is complete when the checklist can reference a named file, API field, state owner, data lifecycle, failure outcome, test boundary, and deployment verification step for every must-ship PRD epic without adding a framework or inventing persistence. This document meets that threshold and intentionally leaves implementation for `$build-checklist` and `$build-project`.
