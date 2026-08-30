# BillWatch

### ⏳ Not submitted yet
Nothing has been sent to Devpost.

Event: [All Things Agentic Hackathon](https://allthingsagentichackathon.devpost.com/)

Category: **Taskmaster**

Live project draft: `BillWatch` (Devpost project ID `1401315`)

Official endpoint value: **2026-09-01T00:00:00Z**; Devpost labels the event timezone as Pacific Time. Reconfirm the displayed countdown before the final action.

## Title and Tagline

**Title:** BillWatch

**Final recommended tagline:** An evidence-grounded Taskmaster that pauses instead of guessing.

> Use this tagline in the final Devpost form. It replaces the current live tagline, which says BillWatch drafts an appeal even though the public hackathon workflow does not draft or send appeals.

## One-line Summary

BillWatch accepts arbitrary supported medical-bill text, extracts facts with exact source evidence, checks every unique code pair against bounded references, pauses for missing context, and produces a cautious, auditable next step for human review.

## Problem

Medical bills combine codes, dates, amounts, payer rules, and claim context that are difficult for a consumer to investigate. A one-shot AI answer can sound certain even when essential facts or trustworthy reference data are missing.

## Solution

BillWatch turns review into a bounded Taskmaster workflow. It extracts only source-cited facts, checks every supported code pair, validates reference applicability, pauses for specific missing context, resumes after human confirmation, and produces an auditable report with a cautious next step.

## Why This Matters

Consequential workflows need more than fluent text. BillWatch demonstrates that an agent can remove investigative friction while exposing its evidence, failing closed, and returning control to a person before a consequential conclusion or action.

## Key Features

- Arbitrary supported bill text and TXT, CSV, or JSON input.
- Exact evidence spans for accepted codes, dates, amounts, and supported facts.
- Every unique supported code pair evaluated against bounded reference metadata.
- Genuine missing-context pause and fresh-request resume.
- Append-only active-tab timeline with automatic and human events.
- Strict separation between optional Gemini proposals and deterministic decisions.
- Isolated author-written synthetic proof path that cannot affect ordinary analysis.
- Browser-local simulated approval that sends nothing.

## Project story

### Inspiration

Medical bills can be difficult to investigate because important facts are scattered across line items, dates, codes, payer context, and explanation-of-benefits documents. A confident-looking answer can be harmful when the evidence is incomplete. BillWatch was shaped around a different idea: a useful agent should know when to stop, show its evidence, and ask a person for the missing context instead of guessing.

The experience combines TurboTax-style guided questions, a GitHub Actions-style investigation timeline, and a Stripe-style human boundary before a consequential action. The result feels like a calm consumer advocate's office paired with a meticulous evidence laboratory.

### What it does

BillWatch lets a person paste an itemized medical bill or load a supported TXT, CSV, or JSON file. It then:

- validates the request and applies request-size, rate, and pair-expansion limits;
- extracts supported facts such as codes, dates, and amounts with exact source spans;
- rejects extracted code facts that do not occur in their cited source evidence;
- deduplicates supported codes and evaluates every unique pair;
- checks bounded reference metadata, including scope, version, effective period, checksum, verification, and licence basis;
- records only investigation stages that actually occurred;
- pauses when required payer, date, claim, beneficiary, or modifier context is missing;
- resumes through a fresh server request after a person supplies supported context, while retaining the first attempt in the active browser tab; and
- reports a bounded status and safe next step without claiming that a bill is definitely incorrect.

The public proof of concept uses statuses such as `INSUFFICIENT_CONTEXT`, `REFERENCE_UNVERIFIED`, `NO_MATCHING_RULE`, `NO_SUPPORTED_DISCREPANCY_FOUND`, and `POTENTIAL_DISCREPANCY`. Only the last status displays a simulated approval control, and either approval choice stays in page memory and clearly states that nothing was sent.

### The main Taskmaster moment

The guided hackathon example uses one author-written synthetic rule for `BW-DEMO-001` and `BW-DEMO-002`. These are demonstration identifiers, not CPT or HCPCS codes and not CMS, AMA, insurer, payer, or clinical data.

The first attempt deliberately lacks three required facts. BillWatch extracts both identifiers with exact evidence, checks the bounded synthetic reference, and pauses instead of guessing. A person supplies the service date and confirms the shared date and beneficiary-or-claim context. Resume creates a second server request, records the human confirmation, retains Attempt 1, and reaches a cautious `POTENTIAL_DISCREPANCY` review signal only because every deterministic gate for the synthetic rule passed. The final simulated approval is browser-local and sends nothing.

### How we built it

BillWatch preserves a deliberately small stack:

- Python's built-in HTTP server and one POST-only `/investigate` endpoint;
- inline HTML, CSS, and JavaScript in `app.py`;
- Gemini 3.5 Flash through the Google GenAI SDK for optional ordinary literal-fact extraction;
- deterministic Python validation and adjudication for source integrity, pair generation, context gates, reference applicability, and final status;
- one isolated deterministic synthetic-demo module reached only by an exact demo flag; and
- Google Cloud Run for the public service.

Ordinary Gemini output is treated as untrusted input. The model may propose literal facts, but it cannot determine payer scope, make a reference authoritative, set the final status, or approve an action. Exact source-span validation and deterministic gates own those decisions. The synthetic guided demo is deterministic and does not depend on Gemini.

Browser progress is intentionally held only in one JavaScript investigation object in the active page. There are no server sessions, user accounts, case records, `localStorage`, or `sessionStorage`. Refreshing or closing the tab clears the investigation.

### What existed before the hackathon and what was added

The original BillWatch application already accepted arbitrary medical-bill text, extracted exact source-cited facts, generated unique code pairs, used fail-closed reference checks, separated AI proposals from deterministic decisions, enforced safety limits, and rejected `GET /investigate`.

The hackathon work added the guided Taskmaster experience: truthful stage metadata, structured missing-context fields, a real pause and fresh-POST resume loop, retained browser attempts, human timeline events, honest Retry states, the isolated synthetic proof path, the browser-local simulated approval boundary, expanded safety tests, a prominent active-tab notice, and the verified public Cloud Run revision.

### Challenges

The hardest design problem was demonstrating a useful discrepancy workflow without presenting protected or unverified reference data as authoritative. BillWatch solves this with strict separation. The ordinary illustrative NCCI relationship remains explicitly unverified and cannot support a discrepancy. A separate, unmistakably labelled author-written synthetic rule proves the fully gated workflow without being represented as medical or payer data.

A second challenge was making pause and resume auditable without adding a database inside a ten-hour implementation limit. Page-memory attempts preserve the first result and human confirmation during the active tab, while every Resume still makes a fresh POST and re-runs the deterministic checks.

### Accomplishments

- A genuine pause -> human confirmation -> fresh-request resume loop.
- Exact evidence remains visible while the source is locked.
- Earlier attempts remain expandable and the newest report becomes primary.
- Unverified evidence cannot produce a discrepancy signal.
- The synthetic path is strictly isolated from ordinary medical-bill analysis.
- Simulated approval performs no network, navigation, download, clipboard, or external action.
- Full local regression increased from 488 to 533 passing tests with no accepted regression.
- The existing Cloud Run service was updated in place and publicly verified.

### What we learned

Agentic behavior is not only about completing more steps automatically. For consequential domains, the most credible agent may be the one that exposes its evidence, names uncertainty, and deliberately transfers control to a person at the right moment. We also learned that a visible stage timeline is valuable only when it is truthful: a failed request must never inherit completed stages or a reassuring final status.

### What's next

A production path would require formally licensed and current reference data, a privacy and security review, stronger production authentication and abuse controls, accessibility and reliability work, cost monitoring, and a carefully designed consent model for any durable case history. Real messaging, appeals, provider contact, payer contact, payment actions, and external sending remain intentionally outside this proof of concept.

## How We Used AI

- **Google AI model:** Gemini 3.5 Flash (`gemini-3.5-flash`).
- **Google SDK:** Google GenAI SDK (`google-genai`).
- **Model role:** propose literal facts from ordinary bill text; output remains untrusted until deterministic exact-evidence validation succeeds.
- **Deterministic role:** validate evidence, generate pairs, evaluate context and reference gates, and assign bounded statuses.
- **Google Cloud service:** Cloud Run in `us-central1`.
- **Verified service:** `billwatch`, revision `billwatch-00014-ngm`, receiving 100% of traffic.
- **Public URL:** [https://billwatch-403260979598.us-central1.run.app](https://billwatch-403260979598.us-central1.run.app)

### Data sources

- The bill text supplied by the user for the current request; it is processed transiently rather than stored as a BillWatch case.
- A small checked-in illustrative NCCI relationship that is explicitly unverified and therefore blocked from supporting a discrepancy.
- Exactly one separately stored author-written synthetic demo rule, used only to prove the gated workflow and never represented as official or clinical data.

## Judging alignment

- **Innovation and operational utility (40%):** the central capability is a genuine missing-context pause, human confirmation, and safe resume rather than an unsupported one-shot answer.
- **Architectural discipline and technology stack (30%):** Gemini 3.5 Flash proposes ordinary literal facts, deterministic gates own consequential decisions, and the public service runs on Cloud Run with a deliberately isolated synthetic path.
- **Demo and production readiness (30%):** the service is publicly reachable, the core journey is repeatable, 533 tests pass, five screenshots are prepared, and the video plan includes visible Cloud backend proof and fail-closed safety cases.

## How We Used Codex

Codex guided the project through onboarding, scope, product requirements, technical specification, a 12-item build checklist, implementation, verification pauses, deployment, and this submission-preparation pass. It first created a verified recovery archive and established a 488-test baseline. It then extended inspected components in small slices, stopped at three mandatory safety checkpoints, corrected only narrowly explained stale test expectations after participant approval, performed local and public browser verification, ran privacy and secret inspections, and updated only the verified existing Cloud Run service.

The participant made the product and safety decisions; Codex implemented and verified them. Gemini remains part of the product's ordinary extraction path, while Codex was the development collaborator.

## Architecture

The public flow is:

```text
Browser input and active-tab investigation state
                    |
                    v
         POST /investigate on Cloud Run
                    |
          +---------+---------+
          |                   |
Ordinary evidence path   Exact synthetic-demo flag
Gemini may propose       One isolated author-written rule
literal facts            Deterministic extraction
          |                   |
          +---------+---------+
                    |
     Exact-evidence and applicability gates
                    |
     Fail-closed status and auditable report
                    |
 Human confirmation / browser-local approval only
```

Devpost-ready architecture upload: `output/pdf/billwatch-hackathon-architecture.pdf`

The older root-level `billwatch-architecture.svg` describes a deeper appeal-drafting path and should not be uploaded for this public proof. The replacement PDF accurately shows the public browser-memory workflow, Gemini/deterministic boundary, Cloud Run API, isolated demo path, fail-closed outcomes, and non-sending human control.

## Testing Instructions

### Public verification

1. Open the [public BillWatch URL](https://billwatch-403260979598.us-central1.run.app).
2. Confirm the **Active browser tab only** notice is visible.
3. Load the separate **Hackathon Demo - synthetic** example and choose **Analyze Bill**.
4. Confirm Attempt 1 pauses with exact source evidence and only the three missing-context questions.
5. Enter `2026-08-01`, confirm the same date and same beneficiary-or-claim context, and choose **Resume investigation**.
6. Confirm Attempt 1 remains expandable, a new request ID appears, and the newest report shows the bounded synthetic `POTENTIAL_DISCREPANCY` signal.
7. Choose either simulated approval decision and confirm **Nothing was sent.**
8. Refresh and confirm that the active-tab investigation disappears.
9. For the safety proof, load the multi-code example and confirm that the illustrative `45378` / `45380` relationship is `REFERENCE UNVERIFIED` and never exposes the approval card.

### Local setup

Python 3.11 or newer is recommended.

```text
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -p "test*.py"
python -m pytest -q
```

Run without `GEMINI_API_KEY` for the deterministic offline ordinary extractor:

```text
# Windows PowerShell
$env:PORT = '8091'
python app.py
```

Open `http://127.0.0.1:8091/`. Supplying `GEMINI_API_KEY` enables the ordinary Gemini extraction path; the synthetic guided demo remains deterministic.

### Recorded evidence

- Final unittest regression: **533 passed** in 2.241 seconds; pre-change baseline 488.
- Final pytest regression: **533 tests plus 24 subtests passed** in 5.60 seconds; baseline 488 tests plus 10 subtests.
- Focused synthetic module: **12 passed**.
- Synthetic/analyzer/API isolation group: **42 passed**.
- Analyzer/API/state-machine group: **40 passed**.
- Public `/health` and `/` succeeded; `GET /investigate` remained HTTP 405.
- The synthetic pause and resume used distinct request IDs and retained Attempt 1.
- A public privacy marker produced zero Cloud Logging matches for the verified revision.
- Docker was unavailable on the Windows build host; Google Cloud successfully built the unchanged Dockerfile for the verified revision.

## Public Demo Link

[https://billwatch-403260979598.us-central1.run.app](https://billwatch-403260979598.us-central1.run.app)

The verified public service is Google Cloud Run revision `billwatch-00014-ngm` in `us-central1`.

## Public Repository Link

[https://github.com/macbere/billwatch](https://github.com/macbere/billwatch)

The URL was supplied by the participant, and its public Git remote was reachable on 2026-08-30 at HEAD `679367a752cbf2cbc87337b3edcb0920e8c1518c`. Codex has not pushed the current local hackathon build to this repository. Because this workspace has no `.git` directory, the remote cannot yet be treated as synchronized with the tested and deployed local build.

If the repository remains private, grant access to the official judge accounts named in the Devpost form. Run a final secret and privacy scan before making any repository public.

## Demo Video

**Video URL:** `[PARTICIPANT WILL ADD WHEN READY]`

Recommended length: approximately four minutes.

Beginner recording instructions and a word-for-word presentation plan are saved at `docs/hackathon-build/demo-recording-guide.md`. The safest recording uses only BillWatch's built-in synthetic or illustrative examples and avoids showing personal bills, API keys, notifications, unrelated tabs, or Cloud Console secrets.

**0:00-0:25 - Problem and promise**

Explain why medical-bill review needs evidence and a safe pause, not confident guessing. State that BillWatch provides review support rather than medical, legal, insurance, coding, or payment advice.

**0:25-0:50 - Architecture and live backend**

Show the architecture PDF, the public Cloud Run URL, and `/health`. Name Gemini 3.5 Flash, the Google GenAI SDK, Cloud Run, and the deterministic trust boundary.

**0:50-1:25 - Start the synthetic journey**

Show the active-tab notice and the separately labelled author-written synthetic card. Load the example, analyze, and point out the exact spans for `BW-DEMO-001` and `BW-DEMO-002`.

**1:25-2:05 - The central pause**

Show `INSUFFICIENT CONTEXT`, the truthful completed-stage timeline, the locked source, and the three supported questions. Explain that BillWatch paused instead of guessing.

**2:05-2:45 - Human confirmation and resume**

Enter `2026-08-01`, confirm the two context gates, and Resume. Show the human timeline event, fresh request ID, retained Attempt 1, reference metadata, and bounded `POTENTIAL DISCREPANCY` wording.

**2:45-3:15 - Consequential-action boundary**

Choose a simulated approval decision and emphasize the visible **Nothing was sent** message. State that no appeal, message, payment, download, or external action occurs.

**3:15-3:40 - Fail-closed safety proof**

Open a fresh tab, run the multi-code example, and show that the illustrative NCCI relationship remains `REFERENCE UNVERIFIED` and cannot produce the approval control.

**3:40-4:00 - Verification and close**

Show the 533-test result, verified Cloud Run revision, and one-sentence takeaway: BillWatch makes evidence and human control part of the workflow.

## Screenshot Shot List

1. `docs/hackathon-build/submission-assets/01-billwatch-start.png`

   **Caption:** BillWatch begins with arbitrary bill input, an active-tab privacy notice, and a separately labelled synthetic guided example.

2. `docs/hackathon-build/submission-assets/02-missing-context-pause.png`

   **Caption:** BillWatch preserves exact evidence and pauses for three specific context fields instead of guessing.

3. `docs/hackathon-build/submission-assets/03-resumed-bounded-result.png`

   **Caption:** Human confirmation creates a fresh request, retains Attempt 1, and produces a bounded synthetic review signal only after every deterministic gate passes.

4. `docs/hackathon-build/submission-assets/04-browser-local-approval.png`

   **Caption:** The simulated approval decision is recorded only in the active browser tab and clearly states that nothing was sent.

5. `docs/hackathon-build/submission-assets/05-unverified-reference-blocked.png`

   **Caption:** An illustrative unverified reference is visibly blocked from supporting a discrepancy.

## TODO Official Form Fields

| Field | Draft answer | Status |
|---|---|---|
| Submitter Type | Individuals | Confirmed by participant |
| Country of residence | Nigeria | Confirmed by participant |
| Category | Taskmaster | Ready |
| Organization name | N/A | Confirmed by participant |
| Project start date (MM-DD-YY) | 08-07-26 | Confirmed by participant; within the official submission period |
| Repository URL | https://github.com/macbere/billwatch | Public remote reachable; latest local hackathon changes are not pushed or verified there |
| Reproducible testing instructions in README | Yes | Ready |
| Hosted URL | https://billwatch-403260979598.us-central1.run.app | Ready |
| Additional testing instructions | Use the public and local steps above | Ready |
| Google SDK used | Google GenAI SDK (google-genai) | Ready |
| Google Cloud service | Cloud Run | Ready |
| Architecture diagram | `output/pdf/billwatch-hackathon-architecture.pdf` | Ready for upload |
| Google AI model | Gemini 3.5 Flash (`gemini-3.5-flash`) | Ready |
| Demo video URL | `[PARTICIPANT WILL ADD WHEN READY]` | Required deliverable still outstanding |
| Public content URL | `[OPTIONAL]` | Optional |
| Social post URL | `[OPTIONAL]` | Optional |

### Eligibility check

The participant confirmed `08-07-26` as the project start date. Live Devpost data says the submission period began at `2026-08-04T14:45:00Z`, and the required field states that projects must be newly created during that period. The confirmed date falls within that period, so the previous start-date conflict is resolved.

### Live Devpost draft snapshot

A read-only check on 2026-08-30 confirmed that Devpost project `BillWatch` (project ID `1401315`) remains a draft with no completed entry timestamp. Its live description, hosted URL, and video URL are still empty, and its live tagline is an older version. The final local tagline, write-up, hosted URL, and other prepared answers in this document still need to be applied during the separate final workflow. No Devpost fields were changed by `$prepare-submission`.

## Submission Readiness Notes

- [x] Confirm the in-period project start date as `08-07-26`.
- [x] Confirm submitter type, country of residence, and organization wording.
- [x] Provide a publicly reachable GitHub repository URL.
- [ ] Synchronize the current tested hackathon build to the repository and verify that its key code, tests, README, and submission evidence are present.
- [x] Use the new Devpost-ready architecture PDF, not the older appeal-oriented SVG.
- [x] Five public-demo screenshots are captured with suggested captions.
- [ ] Record and upload the approximately four-minute demo video, including visible Cloud Run backend proof.
- [x] Select the final bounded tagline for the Devpost form.
- [ ] Apply the final local tagline, write-up, hosted URL, required answers, and architecture file to the live Devpost project during the separate final workflow.
- [ ] Run one final `$prepare-submission` pass after the missing answers and URLs are available.

## Known Limitations

- Progress exists only in the active browser tab and disappears on refresh or tab close.
- Raw bill text is processed transiently; there is no durable BillWatch case store.
- The checked-in ordinary reference snapshot is illustrative and not current official NCCI data.
- The synthetic public rule is author-written demonstration evidence, not medical, clinical, CMS, AMA, insurer, or payer data.
- Simulated approval cannot send, publish, download, contact anyone, or change a payment.
- The proof of concept is not a production compliance solution for protected health information.
- A production release requires formal privacy, security, licensing, accessibility, reliability, and cost review.

## Claim guardrails

Do not say that BillWatch proves a bill is wrong, detects fraud, provides professional advice, uses current official NCCI data, sends appeals, routes real external approvals, preserves history after refresh, or exposes the deeper internal pipeline as the public workflow.
