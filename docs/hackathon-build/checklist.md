# Build Checklist

Status: Build complete. All 12 checklist items passed their available gates. Docker is not installed on this host, so the unavailable local container run remains documented; the existing Cloud Run service built the unchanged Dockerfile successfully.

## Build Preferences

- **Build mode:** Autonomous. This choice locks when implementation starts. Codex executes the checklist between the three mandatory pauses without re-asking routine technical questions.
- **Comprehension checks:** Checkpoint-only. At each pause, Codex explains in plain language what changed, what the tests proved, any remaining concern, and exactly what the participant should look at.
- **Git:** No Git commits are assumed because this folder is not currently recognized as a Git working tree. Before code changes, create and verify a dated recoverable backup. Do not initialize Git or use destructive Git commands as an unrequested workaround.
- **Verification:** Yes. Stop and wait after (1) the recoverable backup and baseline, (2) isolated synthetic-rule and API tests, and (3) browser pause/resume, timeline, and simulated-approval verification before deployment.
- **Check-in cadence:** Autonomous between mandatory pauses. A failed or unexplained safety test also forces an immediate stop.
- **Timebox:** 10 hours total. The twelve tasks are budgeted for about 9 hours 45 minutes, leaving a small contingency.
- **Protected priority:** Preserve existing behavior and tests first; then protect pause -> human confirmation -> fresh-POST resume; then the truthful timeline; then the simulated approval presentation.
- **Central wow moment:** Missing context makes BillWatch pause rather than guess; a person confirms the context; BillWatch safely resumes to a bounded `POTENTIAL_DISCREPANCY` using unmistakably synthetic evidence; a browser-local approval decision is recorded and sends nothing.
- **Scope guard:** No new framework, database, account, official NCCI import, real appeal, external message, payment action, durable persistence, or broad redesign.

## Checklist

- [x] **1. Create the recovery point and record the complete baseline (60 min)**
  Spec ref: `spec.md > Test Plan > Phase 0: Backup and baseline`
  What to build: Confirm the exact workspace, create a dated backup of the source, tests, configuration, and planning documents before editing application code, verify that the backup can be read, install only the existing `requirements-dev.txt` dependencies, and record full and focused pre-change test results. Do not alter application behavior in this task.
  Acceptance: A recoverable pre-build copy exists; its path and verification are recorded; the full `unittest` and `pytest` baselines have exact counts; the known scope-critical suites run; and no unexplained regression is accepted as normal.
  Verify: Run `python -m pip install -r requirements-dev.txt`, `python -m unittest discover -s tests -p "test*.py"`, `python -m pytest -q`, and `python -m unittest tests.test_arbitrary_analysis tests.test_app_routes tests.test_state_machine`. Confirm the recorded backup with `Test-Path <recorded-backup-path>` and open its manifest or representative files. **Verification pause 1:** stop, explain the backup and baseline in beginner-friendly language, report any pre-existing failures separately, and wait for approval to continue.

- [x] **2. Build the isolated synthetic evidence module test-first (45 min)**
  Spec ref: `spec.md > Synthetic Rule Contract`
  What to build: Add `billwatch/synthetic_demo.py` and `tests/test_synthetic_demo.py` with exactly one public author-written rule for the unordered `BW-DEMO-001` / `BW-DEMO-002` pair, exact source spans, immutable provenance, effective dates, licence basis, demo-only scope, canonical SHA-256 integrity data, and deterministic context gates. Leave ordinary code recognition, the unverified NCCI fixture, and the deeper internal plan-policy fixture untouched.
  Acceptance: Exactly one public demo rule exists; every label is unmistakably synthetic; both exact identifiers must occur in their cited spans; checksum and metadata checks pass; missing context pauses; effective-period or gate failures fail closed; and only all passed gates may yield `POTENTIAL_DISCREPANCY`.
  Verify: Run `python -m unittest tests.test_synthetic_demo` and inspect the focused failures before changing any ordinary analyzer or UI code.

- [x] **3. Add honest stage and missing-context metadata without changing ordinary results (45 min)**
  Spec ref: `spec.md > POST /investigate Contract > Backward-compatible optional response fields`
  What to build: Extend `billwatch/arbitrary_analysis.py` with ordered `completed_stages`, structured `missing_context_fields`, non-user-fixable `blocking_context`, `can_resume`, and `analysis_mode`. Append a stage only after the work occurred and preserve all existing response fields, status precedence, pair expansion, exact evidence, limits, and fail-closed semantics.
  Acceptance: Ordinary arbitrary bills retain their existing facts, pair counts, pair statuses, and overall statuses; three unique codes still create three pairs; zero-pair and failed extraction paths do not claim reference checks; and an unverified or unavailable reference is never misclassified as user-repairable context.
  Verify: Run `python -m unittest tests.test_arbitrary_analysis`, including focused assertions for ordinary-result compatibility, ordered stages, structured fields, and the existing `REFERENCE_UNVERIFIED` path.

- [x] **4. Route the demo through the existing API and prove isolation (45 min)**
  Spec ref: `spec.md > POST /investigate Contract > Optional synthetic-demo request field`
  What to build: Keep the single `POST /investigate` endpoint in `app.py`. Strictly accept only `demo_mode: "hackathon_synthetic_v1"`, route that request to the isolated module, omit the field from ordinary requests, reject every unknown type or value with HTTP 400, preserve size/rate/content-type limits, and return the backward-compatible result plus optional metadata. Each resume-like direct POST must be independently evaluated with a new request ID.
  Acceptance: Ordinary requests remain compatible and cannot access synthetic evidence; the exact demo flag reaches exactly one synthetic rule; invalid, boolean, numeric, empty, and case-variant flags fail closed; raw bill text is not added to response metadata; `GET /investigate` remains 405; and unverified ordinary evidence still cannot yield a discrepancy.
  Verify: Run `python -m unittest tests.test_synthetic_demo tests.test_arbitrary_analysis tests.test_app_routes`, then rerun the three scope-critical suites from task 1. **Verification pause 2:** stop, explain how the tests prove the fake demo data cannot leak into ordinary medical-bill analysis, list the exact passing counts, and wait for approval.

- [x] **5. Establish the browser-only investigation shell and clear session boundaries (45 min)**
  Spec ref: `spec.md > Browser Memory Model`
  What to build: Extend the existing inline HTML/CSS/JavaScript in `app.py` with the prominent active-tab-only privacy notice, the separate Hackathon Demo card, and one page-memory `investigation` object holding the bill text, context, attempts, timeline, state, and simulated decision. Preserve the dark-navy design, ordinary form, disclaimer, TXT/CSV/JSON support, and calm language. Add confirmation before Start New or Load Demo clears an active investigation.
  Acceptance: No storage API, cookie, unload transmission, account/history promise, or bill text in a URL is introduced; the ordinary form remains primary; the demo labels its identifiers and rule as author-written and non-medical; cancelling reset changes nothing; confirming reset returns to a clean form; and refresh naturally clears progress.
  Verify: Run `python -m unittest tests.test_app_ui_interactions` and inspect `app.py` for `localStorage`, `sessionStorage`, IndexedDB, cookie, beacon, and unload-send usage; none may be used for investigation state.

- [x] **6. Implement the real missing-context pause and safe fresh-POST resume (60 min)**
  Spec ref: `spec.md > End-To-End Data Flow > Resume`
  What to build: Add a shared request helper and state transitions for Analyze and Resume. On a resumable response, retain exact evidence, lock bill/file inputs, show only the returned supported missing-context controls with plain-language reasons, validate those controls, append the human confirmation, and make a fresh `POST /investigate` with the same browser-held source and updated context. Append the new attempt rather than replacing the first, make the newest report primary, and prevent duplicate or out-of-order clicks.
  Acceptance: The synthetic example reliably pauses with missing context; the first attempt and pause reason remain visible; only permitted context can change; Resume is enabled only with acceptable values; a new request re-evaluates all gates; user-confirmed context is distinct from source evidence; and a wrong source fact requires Start New rather than in-place editing.
  Verify: Run `python -m unittest tests.test_app_ui_interactions tests.test_app_routes`. Locally perform the synthetic first request and resumed request, confirming two different request IDs and that attempt 1 remains append-only.

- [x] **7. Render a truthful timeline and honest retry/failure states (45 min)**
  Spec ref: `spec.md > Failure Strategy`
  What to build: Render only server-returned completed stages plus real browser events, distinguish automatic and human entries, keep earlier attempts under compact `<details>`, and add Retry for valid submissions that fail. Invalid input must create no investigation; failed requests must preserve safe browser input without inventing final findings or completed stages; Retry must append a new attempt.
  Acceptance: The visible order can show received, extracted, pairs generated, references checked, context evaluated, paused, human context supplied, resumed, final result, and later approval only when each occurred; failed work never becomes no-match or no-discrepancy; processing controls cannot be double-activated; and first-run state contains no fabricated ID, report, stage, or approval.
  Verify: Run `python -m unittest tests.test_app_ui_interactions tests.test_app_routes`, then force one failed request locally and confirm Retry retains input, adds no false completion, and records any later success as a separate attempt.

- [x] **8. Add the simulated approval boundary with zero external effect (30 min)**
  Spec ref: `spec.md > End-To-End Data Flow > Simulated approval`
  What to build: Render the proposed-action card only when the newest top-level status is `POTENTIAL_DISCREPANCY`. Add `type="button"` Approve and Reject handlers that update only `approvalDecision`, append one human timeline event, rerender, and state “Nothing was sent.” Do not connect copying, downloading, fetching, navigation, forms, files, messages, or any external integration.
  Acceptance: Pause, no-match, no-supported-discrepancy, error, and `REFERENCE_UNVERIFIED` states never show approval; either decision leaves the report intact; approval language remains cautious; and neither choice sends, stores, publishes, downloads, or creates anything.
  Verify: Run `python -m unittest tests.test_app_ui_interactions`. Inspect the approval handler to confirm it cannot call the request helper or another side-effect path.

- [x] **9. Prove the complete browser story and safety cases (45 min)**
  Spec ref: `spec.md > Test Plan > Manual browser verification`
  What to build: Start BillWatch locally in deterministic offline mode and perform the main synthetic journey plus ordinary input, file-loading, invalid-input, no-match, unverified-reference, retry, reset, refresh, keyboard, mobile-width, evidence, and metadata checks. Use the browser Network panel to verify exactly one initial POST, one new POST on Resume, and no request, download, navigation, or clipboard action on Approve or Reject.
  Acceptance: The central wow moment works end to end; exact evidence stays visible; the source locks during pause; attempt 1 remains expandable; the resumed synthetic result is cautiously bounded; ordinary unverified evidence cannot show approval; no-match language is not a clean-bill guarantee; reset needs confirmation; refresh clears progress; and the interface remains readable and keyboard-usable.
  Verify: Complete and record all 14 manual checks in `spec.md > Test Plan > Manual browser verification`, including screenshots or concise evidence notes. **Verification pause 3:** stop before deployment, show the participant the working pause -> confirmation -> resume -> bounded result -> local-only decision flow, explain every safety proof in plain language, and wait for approval to deploy.

- [x] **10. Run the final local regression, privacy review, and container gate (45 min)**
  Spec ref: `spec.md > Test Plan > Full regression and final evidence`
  What to build: Run the full automated suites, compare counts with task 1, inspect the final source for persistence, logging, synthetic-data leakage, or external-action regressions, and build/start the existing container locally when Docker is available. Record any environmental limitation honestly rather than calling a partial run complete.
  Acceptance: No new regression remains; all focused safety tests pass; no raw bill or browser investigation is logged or persisted; ordinary analysis is unchanged; the container preserves `/health`, `/`, POST-only investigation, offline demo behavior, headers, limits, and `PORT`; and no secret is included in source or image instructions.
  Verify: Run `python -m unittest discover -s tests -p "test*.py"`, `python -m pytest -q`, and the focused commands from tasks 2–4. If Docker is available, run `docker build -t billwatch-hackathon:local .`, start it with `PORT=8080`, and check `http://localhost:8080/health` plus the local demo. Compare exact test counts with the recorded baseline.

- [x] **11. Update the existing Cloud Run service and verify the public revision (60 min)**
  Spec ref: `spec.md > Cloud Run Deployment And Verification`
  What to build: First use read-only Google Cloud commands to resolve the actual project, region, service, current revision, permissions, public access, and existing deployment method. After the participant has approved pause 3, deploy the verified source as a new revision of that existing service without creating a second service or weakening settings. Keep the demo independent of Gemini; if Gemini remains enabled, use the existing Secret Manager boundary. Record revision identity and URL.
  Acceptance: The existing public service—not an inferred replacement—serves the new UI; `/health` and `/` return 200; `GET /investigate` remains 405; ordinary no-match stays cautious; illustrative NCCI stays unverified; synthetic pause/resume works; approval causes no network action; refresh clears history; and logs/deployment output reveal no raw bill or secret.
  Verify: Run `gcloud run services list`, then `gcloud run services describe <verified-service> --region <verified-region>` before deployment. After deployment, use `Invoke-WebRequest` or equivalent against `<deployed-url>/health`, `<deployed-url>/`, and `<deployed-url>/investigate`; complete the public browser smoke checks and record the new revision.

- [x] **12. Prepare the Devpost handoff and rehearse the proof (60 min)**
  Spec ref: `spec.md > Demo And Submission Flow`
  What to build: Update `README.md` and `docs/hackathon-build/build-notes.md` with the active-tab limitation, synthetic evidence labels, AI-versus-deterministic boundary, no-external-action boundary, exact test results, deployed revision, public URL, known limitations, and reproducible demo steps. Gather the project story, screenshots, repository link, verification notes, and a short rehearsal covering the main pause/resume journey and the no-match/unverified safety proofs.
  Acceptance: Handoff materials distinguish existing versus newly added behavior; never portray synthetic data as official; never claim the bill is wrong; never imply approval sends anything or browser history is durable; include evidence for the central wow moment and all submission proof points; and are sufficient to begin submission drafting without changing product scope.
  Verify: Rehearse the deployed story from a fresh tab, check every permitted/prohibited submission claim in `spec.md`, review the screenshots and test/deployment evidence, and confirm the next command is `$prepare-submission`.
