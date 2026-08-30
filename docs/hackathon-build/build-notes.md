# Build Notes

## Guided-build onboarding

- Started the optional guided build path inside Resources.
- Devpost display name recorded as Macdonald Bereiweriso.
- Round 1 completed.
- Project direction: evolve the existing tested BillWatch application into an evidence-grounded Taskmaster workflow for arbitrary medical bills.
- Confirmed scope boundary: medical bills only; exclude general utility, rent, and telephone bills.
- Safety requirements: fail closed; avoid unsupported medical, legal, and insurance claims; use synthetic or properly licensed data; keep exact source evidence and an auditable report; route uncertainty and consequential findings to human approval.
- Preservation requirement: inspect before modifying, retain existing tests, and avoid replacing or rebuilding working components.
- Participant calibration: complete beginner and non-coder; use plain language, small steps, safety backups, and before/after testing for important changes.
- Round 2 completed.

### Round 2 workflow decisions

- Accept pasted itemized bill text or supported TXT, CSV, or JSON uploads. Optional context includes payer/program, service date, modifiers, claim/EOB status, and same-date/same-beneficiary-or-claim confirmation.
- Create an investigation ID and durable audit trail; record validation, source-cited extraction, planning, every unique supported pair check, bounded reference selection, provenance and licence checks, pauses, human decisions, resumed analysis, and final reporting.
- Pause rather than guess when required context is missing or uncertain, when applicability cannot be established, when evidence is unverified/unlicensed/outside its effective period, or when a consequential action is proposed.
- Resume after human correction or confirmation without losing earlier evidence or decisions.
- Final statuses are bounded to: potential discrepancy, insufficient context, reference unverified, no matching rule, and no supported discrepancy found. A matching code pair is never proof that a bill is definitely incorrect.

### Automation and approval boundary

- Safe automatic work: input validation and limits; source-cited extraction; rejection of unsupported facts; code deduplication and pair generation; local reference/provenance/date/checksum/scope/licence checks; missing-context detection; provisional deterministic status; audit records; and a draft safe next-step recommendation.
- A potential-discrepancy label is allowed only when deterministic gates establish all required context and verified reference evidence.
- Mandatory approval: uncertain fact correction; unproven payer/date/beneficiary/claim/modifier context; consequential conclusions; appeals, complaints, messages, or documents; provider/payer contact; payment decisions; sensitive bill storage/sharing/publication; and any use of data whose licence is not established.
- Proof-of-concept boundary: no external sending. An appeal may only be drafted after a supported discrepancy passes all gates, and any future sending capability must require explicit approval.

### Existing implementation facts to verify during inspection

- The public app uses an in-repository ReferenceStore with small illustrative HCPCS and ICD-10 records, one illustrative NCCI PTP relationship, and a synthetic author-written plan-policy fixture.
- The arbitrary-bill public workflow currently queries NCCI code pairs. Its included NCCI relationship is explicitly unverified, so it produces REFERENCE_UNVERIFIED rather than a potential discrepancy.
- A fail-closed NCCI importer and checksum-verified read-only SQLite repository exist deeper in the repository but are not connected to the public workflow. Protected CMS/AMA data must not be downloaded, imported, or published without an appropriate licence.
- Gemini may propose literal facts, but deterministic validation requires exact source spans and requires a code value to appear in its cited span. Offline mode uses an input-driven deterministic extractor.
- Existing gates cover supported CPT/HCPCS-style shapes, bounded pair expansion, all unique pairs, payer, service date, same-date/same-beneficiary-or-claim confirmation, modifiers, evidence verification/effective period, and Medicare/Medicaid/private/unknown scope.
- A deeper internal state machine and pipeline already cover ingestion, extraction, scoping, hypothesis generation, evidence retrieval, verification, conflict checking, adjudication, and conditional appeal drafting. These are not yet the public end-to-end workflow, and the current app must not be described as already routing human approval.

### Proof-of-concept acceptance evidence

- One end-to-end arbitrary-input investigation visibly completes ingestion, exact source-grounded extraction, planning, all pair checks, bounded/versioned evidence lookup, missing/conflicting context detection, a human checkpoint, human correction or confirmation, resumed analysis, and an auditable final report with a safe next action.
- Demo cases include: missing-context pause; no matching rule; a synthetic scenario that legitimately reaches potential discrepancy; unverified evidence blocked from supporting a discrepancy; and an external action blocked until approval.
- Preserve existing arbitrary input, evidence and deterministic safety gates, AI/deterministic separation, provenance/licence controls, evidence model and legal state transitions, privacy/no bill-content logging or storage, offline operation, request/rate/pair limits, POST /investigate safety, all existing tests, and existing working behavior.
- Active shaping: "The app must not be described as already performing human approval routing."
- Active shaping: "Extend inspected components rather than replacing or rebuilding them."

### Round 3 design direction

- Round 3 completed.
- Desired atmosphere: a calm consumer advocate's office combined with a meticulous evidence laboratory; reassuring, trustworthy, methodical, and not overly clinical.
- Preserve the dark navy visual foundation. Use restrained blue/teal accents, strong contrast, readable typography, generous spacing, and evidence cards.
- Avoid excessive red, flashing warnings, crowded dashboards, decorative medical imagery, alarming symbols, and definitive medical presentation.
- Voice: calm guide plus neutral investigator, using plain language and careful uncertainty.
- Demo center: the missing-context pause and resume, supported by the visible evidence trail, as the clearest demonstration of agentic behavior under human control.
- Copy guardrails: avoid "fraud," "illegal," "definitely wrong," "guaranteed error," or pressure to dispute or withhold payment. The proof of concept must not make independently unestablished claims.
- Active shaping: "The emotional center of the demo should be the missing-context pause and resume."
- Guided-build onboarding completed after three rounds. Next stage: Scope.

## Scope stage

- Scope interview started after reading the complete onboarding context.
- Read-only repository inspection confirmed two separate paths: `app.py` plus `billwatch/arbitrary_analysis.py` provide the public arbitrary-input workflow; `billwatch/pipeline.py`, `billwatch/investigation.py`, and `billwatch/state_machine.py` provide the deeper staged domain workflow and fail-closed appeal gate.
- Confirmed public behavior: pasted or TXT/CSV/JSON text input; POST `/investigate`; input and rate limits; exact source-cited fact extraction; every unique code-pair check; bounded result labels; request IDs; and no bill-content/request-header logging.
- Confirmed public gap: the response is currently one-shot. Its visible stage list is static, and the public path does not yet expose a durable human pause, correction, resume, or full state-machine history.
- Confirmed reference boundary: checked-in public NCCI data is illustrative and unverified; the checksum-verified read-only SQLite repository exists but is not wired into the public app.
- Baseline test run: full unittest discovery ran 458 tests but had one import error because `httpx` is not installed in the current Windows environment. No application assertion failure was reported before that loader error.
- Scope-critical baseline: 30/30 tests passed across `tests.test_arbitrary_analysis`, `tests.test_app_routes`, and `tests.test_state_machine`.
- Repository note: this folder is not currently recognized as a Git working tree, so Git cannot yet serve as the requested safety-backup mechanism from this location.

### Confirmed timebox and cut direction

- Hard implementation budget: 10 hours total, including implementation, tests, deployment, and demo preparation.
- Interaction inspiration: TurboTax-style guided missing-information questions and pause/resume; GitHub Actions-style visible stage/evidence timeline; Stripe-style human approval before consequential actions.
- Session model: browser-session-only. Do not persist raw bill text on the server or outside the active browser session. It is acceptable for progress to disappear when the tab closes; document this as a proof-of-concept limitation.
- Synthetic evidence: include exactly one prominently labelled author-written synthetic rule, stored and displayed separately from the unverified illustrative NCCI fixture. Its only purpose is to prove that fully verified synthetic evidence can legitimately reach `POTENTIAL_DISCREPANCY`. Never represent it as official CMS, AMA, insurer, payer, or clinical data.
- Priority order under time pressure: (1) real pause -> human correction or confirmation -> resume; (2) concise evidence and investigation-stage timeline; (3) visible external-action approval gate with no real external action.
- Explicit cuts: official NCCI importing, user accounts, a database, real messaging, appeal sending, payment actions, production persistence, and a broad redesign.
- Preservation requirements remain binding: existing analyzer behavior, safety gates, privacy guarantees, and tests.
- Active shaping: "Please cut scope aggressively for ten hours."

### Final scope decisions

- Approved unmistakably synthetic identifiers such as `BW-DEMO-001` and `BW-DEMO-002`, available only in a prominently labelled synthetic demo path and never represented as real billing codes or official data.
- Approved limiting in-workflow correction to existing context fields. Incorrect source-cited facts require editing the original bill text and starting a fresh investigation.
- Approved leaving the full internal pipeline disconnected from the public app in this timebox. The UI may show only stages that genuinely occur, and the external-action approval control is explicitly simulated and non-sending.
- Optional scope deepening round skipped at the participant's request because no blocking ambiguity remained.
- Scope mandatory beats completed. Deepening rounds taken: 0.
- Created `docs/hackathon-build/scope.md` with the ten-hour must-ship list, explicit cuts, demo path, definition of done, constraints, and submission story.
- Next guided-build stage: PRD.

## PRD stage

- PRD interview started from the approved ten-hour scope.
- Product requirements will stay non-technical and focus on visible behavior, testable acceptance criteria, failure states, and user understanding.
- Existing scope boundaries remain locked unless the participant explicitly changes them.

### Approved core screen behavior

- Preserve the existing bill form and dark-navy design; add a clear browser-session notice, retain the safety disclaimer, and place the synthetic guided example in a separate, prominently labelled Hackathon Demo card.
- On pause, keep extracted evidence visible; show only missing context and why each item matters; present the relevant existing controls and **Resume investigation**; lock the original bill text until the user starts a new investigation.
- On resume, record the human confirmation in the timeline, safely rerun the analysis, show the newest report as primary, and retain the first attempt in a compact expandable timeline.
- Show the simulated proposed-action approval card only after `POTENTIAL_DISCREPANCY`. Approve or Reject records only a browser-local decision and clearly says that nothing was sent.

### Approved PRD edge cases

- Empty or invalid input shows a clear correction message and produces no investigation result.
- If analysis fails, retain the user's browser input, show **Retry**, and never claim that unfinished stages succeeded.
- Starting another investigation or loading the synthetic demo clears the current browser timeline only after confirmation.
- Missing-context, no-match, no-supported-discrepancy, and unverified-reference results never display the simulated approval card.

### PRD completion

- The participant confirmed that mandatory behaviors, acceptance expectations, edge cases, and the ten-hour scope guard are sufficiently defined.
- Optional PRD deepening round skipped at the participant's request. Deepening rounds taken: 0.
- Created `docs/hackathon-build/prd.md` with user journeys, stable epics and stories, observable acceptance criteria, status-specific behavior, first-run and error states, design and language safeguards, explicit timebox cuts, and submission proof points.
- Active shaping: “Only POTENTIAL_DISCREPANCY displays the simulated approval card.”
- Active shaping: “If analysis fails, keep the user's input visible, show Retry, and never claim that unfinished stages succeeded.”
- Next guided-build stage: Technical Spec.

## Technical Spec stage

- Technical-spec interview started from the completed scope and PRD.
- The participant's beginner/non-coder profile requires plain-language architecture choices, conservative changes, explicit file responsibilities, and verification before and after each implementation slice.
- Initial read-only mapping confirms the public product is deliberately small: Python's built-in HTTP server in `app.py`, one POST-only `/investigate` API, inline HTML/CSS/JavaScript, `billwatch/arbitrary_analysis.py` for the public deterministic workflow, and `billwatch/reference_bootstrap.py` plus `billwatch/reference_data.py` for local bounded references.
- Existing deployment assets are already present: `Dockerfile`, `requirements.txt`, a `/health` route, and a documented Google Cloud Run URL. The deployed URL may lag the local working copy.
- Existing browser behavior is one-shot and holds no investigation history. Pause/resume, the attempt timeline, and simulated approval can therefore remain browser-owned without adding a database or server session.
- Existing AI boundary is suitable for preservation: optional Gemini extraction when a key is supplied and deterministic input-driven offline extraction otherwise. Deterministic code remains responsible for accepted evidence and result status.
- Compatibility issue surfaced for participant confirmation: the deeper repository already contains one synthetic plan-policy fixture used by established tests, while the hackathon PRD requires one new public synthetic pair rule using `BW-DEMO-001` and `BW-DEMO-002`. The safest interpretation is exactly one rule in the public Hackathon Demo path while leaving the existing internal fixture untouched and unexposed.

### Approved Spec foundation

- Preserve Python's built-in HTTP server, the inline HTML/CSS/JavaScript interface, and the existing analyzer. Do not add Flask, React, a database, or another application framework.
- Hold the active investigation, attempts, timeline, and simulated approval only in JavaScript page memory. Refreshing or closing the tab clears progress; no server session, `localStorage`, `sessionStorage`, or other browser persistence is added.
- Update the existing public Google Cloud Run deployment for submission rather than relying on a local-only demo.
- Add exactly one new public Hackathon Demo rule for `BW-DEMO-001` / `BW-DEMO-002`. Leave the established deeper internal synthetic plan-policy fixture unchanged and unexposed; “exactly one” applies to the public Hackathon Demo path.
- Active shaping: “Do not introduce Flask, React, a database, or another framework.”
- Active shaping: “Refreshing or closing the tab clears progress.”

### Approved API, state, isolation, and test boundaries

- Keep the single `POST /investigate` endpoint. Add only backward-compatible optional request and response fields for the explicit demo mode, genuinely completed stages, and structured missing context.
- Add one isolated `billwatch/synthetic_demo.py` module. It is reachable only through an explicit, strictly validated Hackathon Demo flag and cannot alter ordinary medical-bill analysis.
- Keep one in-memory JavaScript investigation object in `app.py` containing the browser-held bill text, context, attempts, timeline, current state, and simulated approval decision. Refreshing or closing the tab destroys it.
- Add focused tests proving ordinary analysis remains unchanged, the synthetic path is isolated, Resume performs a fresh POST while retaining the prior browser attempt, unverified evidence remains blocked, failed requests never mark unfinished stages complete, and approval performs no network action.
- The proposed architecture, annotated file map, request/response lifecycle, failure strategy, deployment target, and verification boundary now cover all mandatory Technical Spec beats.
- Mandatory Technical Spec beats completed. Awaiting the participant's optional-deepening choice; no application code has been modified.
- Active shaping: “Add only backward-compatible optional request/response fields.”
- Active shaping: “The synthetic path is isolated.”

### Technical Spec completion

- The participant chose **Write the Spec now** and skipped the optional Technical Spec deepening round. Deepening rounds taken: 0.
- Created `docs/hackathon-build/spec.md` with the locked stack, component architecture, PRD epic traceability, annotated file structure, backward-compatible `POST /investigate` contract, isolated synthetic-rule contract, browser-memory model, end-to-end data flow, failure strategy, AI/deterministic boundary, privacy controls, test plan, dependency documentation links, Cloud Run verification, implementation sequence, and demo flow.
- Verified that the Spec names `app.py`, `billwatch/arbitrary_analysis.py`, the new `billwatch/synthetic_demo.py`, the relevant tests, README/deployment work, and the no-persistence/no-external-action boundaries explicitly.
- No application code was modified during the Technical Spec stage.
- Next guided-build stage: Build Checklist.

## Build Checklist stage

- Build-checklist planning started from the completed Scope, PRD, and Technical Spec.
- The approved Technical Spec already supplies an eight-slice, ten-hour implementation sequence; the checklist will convert it into 8–12 small, testable tasks rather than expand the product scope.
- Before drafting the checklist, the participant will choose whether to co-design the task sequence or hand plan design to Codex, and whether the later build should include explicit look-at-it pauses.
- No application code has been modified during checklist planning.

### Checklist preferences and draft

- The participant handed checklist design to Codex and approved autonomous implementation between explicit verification pauses.
- Mandatory pauses are locked after: (1) recoverable backup and baseline tests; (2) isolated synthetic-rule and API tests; and (3) local browser pause/resume, timeline, and simulated-approval verification before deployment.
- Each checkpoint must explain in plain language what changed, what the tests proved, any concern, and what the participant should inspect.
- Central wow moment: a missing-context pause, human confirmation, safe fresh-POST resume to a bounded `POTENTIAL_DISCREPANCY` using unmistakably synthetic evidence, followed by a browser-local approval choice that sends nothing.
- Checklist deepening rounds: 0. The handoff path uses the participant's required final gut-check instead.
- Created the complete 12-item draft in `docs/hackathon-build/checklist.md`. It remains unlocked pending the participant's final gut-check; implementation has not started.
- Active shaping: “Pause after recoverable backup and baseline tests, isolated synthetic-rule/API tests, and browser verification before deployment.”

### Build Checklist completion

- The participant approved the complete 12-task checklist without changes after the required final gut-check.
- The autonomous build mode, recovery-first requirement, ten-hour scope guard, central wow moment, and all three mandatory verification pauses are now locked for `$build-project`.
- The checklist is finalized at `docs/hackathon-build/checklist.md`; guided-build state now recommends `build-project`.
- No application implementation began during checklist finalization.

## Build execution

### Checklist item 1 — recovery point and complete baseline

- Confirmed workspace: `C:\Users\hp\Documents\Codex\billwatch-system`.
- Confirmed the folder is not a Git working tree; no Git initialization or destructive Git command was used.
- Created the recovery archive outside the project folder: `C:\Users\hp\Documents\Codex\billwatch-system-safety-backups\billwatch-prebuild-20260829-224828.zip`.
- Backup verification: 489,938 bytes; 121 archive entries; all required representative files present; SHA-256 `409D7F39268775A4953A8BFD41F045EAD426761A17A47984FEF21F483939F6FC`.
- Installed only the existing `requirements-dev.txt` dependency set into the existing project `.venv`; system Python was not changed. Verified `google-genai 2.20.0`, `httpx 0.28.1`, and `pytest 9.1.1` imports.
- The first sandboxed dependency download could not access the package index. The approved network-enabled retry completed the same declared installation; this was an environment restriction, not a BillWatch failure.
- Pre-change full unittest baseline: 488 tests ran in 1.954 seconds, all passed.
- Pre-change pytest baseline: 488 tests plus 10 subtests passed in 5.62 seconds.
- Pre-change scope-critical baseline: 30 tests across arbitrary analysis, app routes, and state machine ran in 0.659 seconds, all passed.
- No application source or test code was changed in item 1.
- Verification Pause 1 reached. Checklist item 2 has not started and requires participant approval to continue.

### Checklist items 2 and 3 — passed; item 4 safety stop

- Verification Pause 1 was explicitly approved before implementation resumed.
- Item 2 added the isolated `billwatch/synthetic_demo.py` module and `tests/test_synthetic_demo.py` without changing the existing reference bootstrap or deeper plan-policy fixture.
- Item 2 focused result: 12 tests passed. The tests cover exactly one rule, unmistakably synthetic identifiers, exact source spans, fixed checksum, exact demo-mode validation, missing-context gates, effective-period gates, tamper detection, pair deduplication, and internal-fixture isolation.
- Item 3 added backward-compatible `analysis_mode`, truthful `completed_stages`, structured `missing_context_fields`, `blocking_context`, and `can_resume` metadata while retaining every existing result field and ordinary status behavior.
- Items 2 and 3 combined focused result: 26 tests passed (12 synthetic-module tests and 14 ordinary-analyzer tests).
- Item 4 added a strict exact demo-mode branch to the existing `POST /investigate` path and its initial HTTP contract tests, but item 4 is not complete.
- Item 4 focused run stopped after 16 tests with 1 failed assertion: `test_synthetic_identifiers_without_demo_flag_stay_on_ordinary_path` expected an empty fact list.
- The failure is explained: the ordinary path ignored both synthetic identifiers as codes and returned no synthetic rule, but correctly preserved its existing literal-amount extraction for `$40.00` and `$25.00` in the submitted text.
- Proposed correction requiring participant approval: change the test to assert that the ordinary branch has no `code` facts and no `billwatch_hackathon_demo` reference, while permitting the ordinary analyzer's established amount facts. Then rerun all item 4, combined focused, and scope-critical tests.
- No further implementation or test command was run after this safety stop.

### Checklist item 4 — passed; Verification Pause 2

- The participant approved the narrowly scoped test correction. Only the incorrect assertion changed: the ordinary path must contain no synthetic `code` facts and no `billwatch_hackathon_demo` reference, while its established literal-amount facts remain permitted. No production file changed as part of this correction.
- Combined item-4 focused result: 42 tests ran in 0.878 seconds, all passed (`tests.test_synthetic_demo`, `tests.test_arbitrary_analysis`, and `tests.test_app_routes`).
- Updated scope-critical result: 40 tests ran in 0.796 seconds, all passed (`tests.test_arbitrary_analysis`, `tests.test_app_routes`, and `tests.test_state_machine`).
- Isolation proof in plain language: without the exact demo flag, the request stays on BillWatch's ordinary analyzer. The synthetic identifiers are not accepted as ordinary billing-code facts, the synthetic reference is absent, and ordinary features such as literal-amount extraction continue to work.
- The synthetic module is reachable only through the exact `demo_mode: "hackathon_synthetic_v1"` value. Invalid types and values fail closed; the one author-written rule remains separately labelled and deterministically gated; and ordinary unverified evidence still cannot produce `POTENTIAL_DISCREPANCY`.
- Checklist item 4 is complete. Mandatory Verification Pause 2 has been reached, and checklist item 5 has not started.
- Guided-build state remains intentionally at `learning.current_step: "build"` with `next_command: "build-project"`; `checklist` is already recorded in `learning.completed_steps`. This is the required in-progress state until all checklist items are complete.

### Checklist item 5 — safety stop

- Verification Pause 2 was explicitly approved before implementation resumed.
- Item 5 began with the active-tab-only privacy notice, separate synthetic Hackathon Demo card, one JavaScript page-memory investigation object, and shared confirmation before clearing an active investigation.
- The first `tests.test_app_ui_interactions` run executed 14 tests in 0.656 seconds: 13 passed and 1 failed.
- The failure is explained and limited to assertion capitalization. The rendered notice begins with the visible sentence `Active browser tab only.`, while the new static assertion searched case-sensitively for lowercase `active browser tab only`.
- The required notice and privacy meaning are present. No safety behavior was shown missing, but the approved build rule requires a stop on any failed check.
- Proposed narrow correction requiring participant approval: update only that test expectation to the exact displayed capitalization, then rerun the full item-5 UI suite and the required persistence-source inspection. Checklist item 5 remains incomplete; items 6–9 have not started.

### Checklist item 5 — passed

- The participant approved the one-line capitalization correction. Only the static test expectation changed to match the displayed `Active browser tab only.` sentence.
- Item-5 UI result: 14 tests ran in 0.076 seconds, all passed.
- Persistence-source inspection found 0 uses of `localStorage`, `sessionStorage`, IndexedDB, cookies, `sendBeacon`, or unload transmission hooks in `app.py`.
- The ordinary form remains primary, the synthetic example is separately and unmistakably labelled, reset requires confirmation when an investigation exists, and the investigation object lives only in JavaScript page memory.
- Checklist item 5 is complete. Autonomous work continues with checklist item 6.

### Checklist item 6 — safety stop

- Item 6 added the shared fresh-POST request helper, supported-field-only pause controls, source locking, human confirmation event, append-only attempt handling, processing guard, and Resume request path.
- The combined `tests.test_app_ui_interactions tests.test_app_routes` run executed 36 tests in 0.387 seconds: 35 passed and 1 failed.
- The failure is explained and limited to a stale static assertion. The item-5 test searched for `if(selectedMode===HACKATHON_DEMO_MODE)`, but item 6 intentionally builds every request from the locked active investigation and now checks `if(investigation.mode===HACKATHON_DEMO_MODE)` in `payloadForInvestigation()`.
- This change prevents a later UI selection from altering the active investigation mode and preserves ordinary/demo isolation across Resume. The exact server route tests still passed within the combined run.
- The approved build rule requires a stop on any failed check. No direct local pause/resume check was run after the failure, checklist item 6 remains incomplete, and items 7–9 have not started.
- Proposed narrow correction requiring participant approval: update only the stale static expectation to the investigation-owned mode expression, then rerun the complete 36-test item-6 command before performing the required two-POST local verification.

### Checklist item 6 — passed

- The participant approved the one-line static assertion correction from the temporary UI selection to the active investigation's locked mode.
- Final item-6 combined result: 36 tests ran in 1.306 seconds, all passed (`tests.test_app_ui_interactions` and `tests.test_app_routes`).
- The item-6 manual local flow ran against the current offline build on a dedicated port. Attempt 1 paused at `INSUFFICIENT_CONTEXT` with request ID `67c7313a-c50b-46d8-80f4-b3063a8e06d4`.
- After the person supplied service date `2026-08-01` and confirmed the same-date and same-beneficiary/claim gates, Resume made a fresh POST and reached the bounded synthetic `POTENTIAL_DISCREPANCY` result with request ID `52417b04-209c-4273-a072-bda754760677`.
- The request IDs were distinct. Attempt 1 remained expandable and retained its original ID plus all three original pause reasons; the source text and initial controls remained locked.
- Checklist item 6 is complete. Autonomous work continues with checklist item 7.

### Checklist item 7 — passed

- The interrupted work was audited before being accepted. The final combined item-7 result ran 41 tests in 0.818 seconds, all passed (`tests.test_app_ui_interactions` and `tests.test_app_routes`).
- Source inspection confirmed there is no static stage list. The timeline is built only from server-returned `completed_stages` and real browser events, with automatic and human events visually distinguished.
- A forced local request failure preserved the synthetic source, displayed Retry, and showed only `Attempt 1 started` and `Attempt 1 did not finish`; it did not invent a completed stage or result.
- After the local server was restored, Retry made a new request and recorded a separate successful second attempt. The expandable first attempt retained its `DID NOT FINISH` status and `Failed to fetch` evidence.
- Checklist item 7 is complete. Autonomous work continues with checklist item 8.

### Checklist item 8 — passed

- Item-8 UI result: 30 tests ran in 0.128 seconds, all passed.
- The simulated approval card is hidden unless the newest successful top-level status is exactly `POTENTIAL_DISCREPANCY`. Pause, failure, no-match, and unverified-reference states therefore cannot expose it.
- Approve and Reject are non-submitting buttons. Either choice records one decision in the page-memory investigation, appends one human timeline event, keeps the report visible, and states `Nothing was sent.`
- Direct source inspection of `recordApprovalDecision()` found no request helper, `fetch`, clipboard, navigation, element/file creation, `Blob`, or object-URL path. Synthetic results also suppress the ordinary copy/download review actions.
- Checklist item 8 is complete. Autonomous work continues with checklist item 9.

### Checklist item 9 — passed; Verification Pause 3

- Final item-9 focused result: 48 tests ran in 0.725 seconds, all passed (`tests.test_app_ui_interactions` and `tests.test_app_routes`).
- All 14 mandatory local browser checks passed and are recorded under `spec.md > Test Plan > Manual browser verification`. Evidence includes supported files, invalid-input rejection, exact synthetic source spans, distinct pause/resume request IDs, append-only history, truthful stages, failure/Retry, unverified and no-match gates, both local-only approval choices, confirmation, refresh clearing, mobile width, focus, expansion, and contrast.
- The browser check identified weak white-on-blue primary-button contrast. The single theme accent changed from `#5d8ff2` to `#416fce`; the resulting white-text contrast is 4.78:1. No workflow, evidence, status, or safety behavior changed.
- Final source inspection found zero uses of `localStorage`, `sessionStorage`, IndexedDB, cookies, `sendBeacon`, or unload hooks. The approval handler still contains no side-effect path.
- The temporary 200,001-byte oversized-file fixture was removed after its browser check. The small synthetic TXT/CSV/JSON/unsupported-extension browser fixtures remain under `tests/fixtures/` for repeatable verification.
- Checklist item 9 is complete. Mandatory Verification/Safety Pause 3 has been reached. Checklist item 10, full regression/container checks, and all deployment work have not started and require participant approval.
- Guided-build state remains intentionally at `learning.current_step: "build"` with `next_command: "build-project"`. No state value changes at this pause, so `.devpost-hackathon-state.json` remains the correct in-progress state rather than being rewritten with an invented status field.

### Checklist item 10 — passed with documented Docker limitation

- Verification/Safety Pause 3 was explicitly approved before deployment work resumed.
- Final full unittest regression: 533 tests ran in 2.241 seconds, all passed. This is 45 more passing tests than the 488-test pre-change baseline.
- Final pytest regression: 533 tests plus 24 subtests passed in 5.60 seconds. The pre-change baseline was 488 tests plus 10 subtests.
- Focused synthetic-module result: 12 tests passed in 0.006 seconds. Focused ordinary-analyzer result: 14 tests passed in 0.027 seconds.
- Combined synthetic/analyzer/HTTP isolation result: 42 tests passed in 0.322 seconds. Updated scope-critical analyzer/routes/state-machine result: 40 tests passed in 0.816 seconds.
- Privacy inspection found zero `localStorage`, `sessionStorage`, IndexedDB, cookie, beacon, or unload persistence references in `app.py`. The server's request logger remains suppressed, and the only runtime `print` reports the listening port rather than bill content.
- Ordinary analyzer/reference modules contain zero imports or identifiers from the public synthetic-demo module. The approval handler still changes only browser state and has no request or document-action call.
- Secret-literal inspection across application source, Dockerfile, and requirement files found zero embedded Gemini-style key literals. `.dockerignore` excludes `.env`, `.env.*`, key, PEM, ZIP, virtual-environment, cache, and backup material.
- Docker is not installed on this Windows host (`docker_not_installed`), so the local image build/start portion could not be executed. This is recorded as an environmental limitation rather than a passing container run. The unchanged Dockerfile and Cloud deployment build will still be verified through the existing deployment method before the public revision is accepted.
- Checklist item 10 is complete under its explicit “when Docker is available” condition. Autonomous work continues with read-only Cloud Run discovery for checklist item 11.

### Checklist item 11 — deployed and publicly verified

- Read-only Google Cloud discovery resolved the existing target before any change: project `gen-lang-client-0537118940`, service `billwatch`, region `us-central1`, public URL `https://billwatch-403260979598.us-central1.run.app`, and pre-deployment revision `billwatch-00013-hz4` at 100% traffic.
- Existing deployment metadata showed a `gcloud` source deployment into the `cloud-run-source-deploy/billwatch` Artifact Registry path. Existing settings included ingress `all`, public `roles/run.invoker` for `allUsers`, max scale 20, concurrency 80, timeout 300 seconds, startup CPU boost, and the established compute service account.
- Built a runtime-only source archive containing 28 files: `app.py`, `Dockerfile`, `requirements.txt`, and the Python files under `billwatch/`. It contained zero environment, Git, test, documentation, cache, key, PEM, backup, or bill-data entries.
- Local archive SHA-256 `A6364D4B863D126AEDE8944F50FCA004745069129C213E2CC561C0A57DCA106C` matched the checksum calculated after upload to Cloud Shell.
- Deployed only the verified existing service with `gcloud run deploy billwatch --source=... --project=gen-lang-client-0537118940 --region=us-central1 --quiet`; no second service was created and no access flag was supplied.
- Google Cloud build `4f0b9853-f899-45be-828f-c8b321a2655b` completed. Revision `billwatch-00014-ngm` became ready and received 100% of traffic at the unchanged public URL.
- Post-deployment inspection confirmed ingress `all`, max scale 20, concurrency 80, timeout 300 seconds, startup CPU boost, the established service account, and the public `roles/run.invoker` / `allUsers` policy remained unchanged.
- Public HTTP smoke results: `/health` returned `status: ok` in the configured live mode; `/` returned HTTP 200 with the active-tab notice and synthetic demo card; `GET /investigate` returned 405.
- Public API behavior passed: ordinary codes `99213` / `93000` returned cautious `NO_MATCHING_RULE`; the illustrative `45378` / `45380` path remained `REFERENCE_UNVERIFIED`; the exact synthetic demo paused with three structured context fields and then resumed to bounded `POTENTIAL_DISCREPANCY`; the two attempts had distinct request IDs; and the same synthetic text without the demo flag produced zero code facts and no demo reference.
- Public browser evidence passed: Attempt 1 request `4a4503ec-12df-461d-8fff-93e8e50c9287` paused with exact spans and locked source; human confirmation produced Attempt 2 request `cba3dd80-1840-46c2-8c37-d5a967be83ef`; Attempt 1 remained expandable; the newest report was primary; approval left the URL and tab set unchanged and displayed `Approved in this browser tab. Nothing was sent.`
- Refresh cleared the bill text, prior result, and approval decision while retaining the active-tab notice.
- Privacy probe `BW-PUBLIC-PRIVACY-20260830-1320` produced zero Cloud Logging matches for revision `billwatch-00014-ngm`. A separate error-level query for the revision also returned zero entries during the verification window.
- Checklist item 11 is complete.

### Checklist item 12 — Devpost handoff and public rehearsal complete

- Updated `README.md` with the public revision and URL, active-tab-only lifecycle, isolated synthetic labels, existing-versus-added behavior, AI/deterministic boundary, reference and licence limits, no-external-action boundary, exact local and public verification evidence, reproducible demo steps, and known proof-of-concept limitations.
- Rehearsed the public story from a fresh browser tab: session notice -> separate synthetic card -> missing-context pause -> exact evidence and bounded reference -> human confirmation -> fresh POST -> retained first attempt -> cautious `POTENTIAL_DISCREPANCY` -> browser-local approval -> `Nothing was sent` -> refresh clearing.
- Rehearsed both short safety proofs: ordinary `99213` / `93000` produced cautious no-match wording, while illustrative `45378` / `45380` remained blocked by `REFERENCE_UNVERIFIED` and never exposed approval.
- Reviewed every permitted and prohibited claim in `spec.md`. Handoff language does not portray the synthetic rule as official data, does not claim a bill is wrong, does not imply approval sends anything, does not describe browser history as durable, and does not present the deeper pipeline or protected reference importer as the public workflow.
- Deployment, public browser, API, local regression, privacy, and screenshot evidence are ready for submission drafting. The public approval-state screenshot was captured during the verification run.
- Repository-link discovery is the only non-build handoff detail not recoverable from this detached, non-Git working folder. No URL was guessed; `$prepare-submission` should obtain the participant's verified GitHub repository URL before finalizing the Devpost draft.
- Build is complete. The next guided command is `$prepare-submission`; no Devpost submission has been attempted.
