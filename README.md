# BillWatch

BillWatch is an evidence-grounded medical-bill investigation proof of concept for the All Things Agentic Hackathon. A person can paste arbitrary supported medical-bill text or choose a TXT, CSV, or JSON file. BillWatch extracts literal facts with exact source evidence, evaluates every unique code pair, checks bounded reference metadata, pauses when required context is missing, and produces a cautious report for human review.

BillWatch does not claim that a bill is definitely wrong. It does not provide medical, legal, insurance, coding, or payment advice.

## Hackathon required stack

BillWatch is submitted to the **Taskmaster** category of the **All Things Agentic Hackathon**.

- **Google AI:** Gemini 3.5 Flash (`gemini-3.5-flash`)
- **Google Agent Framework:** Google GenAI SDK (`google-genai`)
- **Google Cloud infrastructure:** Google Cloud Run in `us-central1`
- **Ordinary-input production path:** Gemini proposes literal facts; deterministic validation and gates control what can become an accepted result.
- **Offline local fallback:** deterministic extraction exists for reproducible testing when `GEMINI_API_KEY` is absent.
- **Synthetic guided proof:** intentionally deterministic and isolated from ordinary Gemini analysis.

The offline fallback does not replace Gemini in the submitted architecture. It allows reproducible local testing without requiring a judge to provide a credential.

## Submitted architecture

BillWatch uses one canonical architecture diagram across GitHub, Devpost, and the demo video:

**[`output/pdf/billwatch-hackathon-architecture.pdf`](output/pdf/billwatch-hackathon-architecture.pdf)**

That diagram represents the submitted public Taskmaster workflow in `app.py`: browser input and active-tab state, the Google Cloud Run API, the ordinary Gemini 3.5 Flash / Google GenAI SDK evidence path, the isolated deterministic synthetic-demo path, deterministic trust gates, fail-closed outcomes, and the human-controlled report boundary.

[`ARCHITECTURE.md`](ARCHITECTURE.md) provides supporting technical explanation of the same submitted architecture and documents the deeper internal `billwatch/pipeline.py` module separately. The deeper pipeline is supporting engineering architecture and regression coverage; it is not represented as the currently exposed public web product.

The public workflow performs the investigative heavy lifting automatically: request validation, literal-evidence extraction, exact-evidence validation, candidate-pair generation, bounded reference checks, applicability gates, missing-context identification, and cautious result generation. Human input is requested only when evidence required for a safe determination is genuinely absent or at the final simulated consequential-action boundary.

## Public proof of concept

- URL: https://billwatch-403260979598.us-central1.run.app
- Cloud Run service: `billwatch`
- Region: `us-central1`
- Verified revision: `billwatch-00014-ngm`
- Traffic: 100% to the verified revision

The investigation and approval state exists only in the active browser tab. Refreshing or closing the tab clears it. Raw bill text is processed transiently by the server and is not written to BillWatch application logs or durable storage. When the public service has Gemini enabled, ordinary extraction may send the submitted text to Gemini; the synthetic guided demo is deterministic and does not depend on Gemini.

## Hackathon development history

BillWatch was created during the All Things Agentic submission period. Earlier hackathon iterations established arbitrary medical-bill input, exact source-cited fact extraction, unique code-pair generation, fail-closed reference checks, deterministic decision boundaries, safety limits, and rejection of `GET /investigate`.

Later hackathon iterations extended those inspected components with:

- truthful completed-stage and structured missing-context metadata;
- one isolated, explicitly selected synthetic demo path;
- a real missing-context pause and fresh-POST Resume flow;
- an append-only browser timeline with human confirmation events;
- a compact retained view of earlier attempts;
- honest failure and Retry states;
- a simulated browser-local approval boundary that sends nothing; and
- a prominent active-tab-only privacy notice.

It does not connect the deeper internal pipeline to the public workflow, import official NCCI files, add accounts or a database, send an appeal, contact a provider or payer, or perform a payment action.

## Guided synthetic demonstration

The separate **Hackathon Demo · synthetic** card uses exactly one public author-written rule for `BW-DEMO-001` and `BW-DEMO-002`.

These are demonstration identifiers. They are not CPT or HCPCS codes and are not CMS, AMA, insurer, payer, or clinical data. The rule is stored separately from the illustrative unverified NCCI fixture and can be reached only with the exact internal demo-mode value.

To reproduce the main proof:

1. Open the public URL and note **Active browser tab only.**
2. Select **Load synthetic guided example**.
3. Select **Analyze Bill** without adding context.
4. Confirm that BillWatch pauses at `INSUFFICIENT_CONTEXT`, keeps both exact identifier spans visible, and asks only for service date, same-date confirmation, and same-beneficiary/claim confirmation.
5. Enter `2026-08-01`, select both confirmations, and choose **Resume investigation**.
6. Confirm that the timeline records the human input, Attempt 1 remains expandable, a new request ID appears, and the newest result is the bounded `POTENTIAL_DISCREPANCY` review signal.
7. Select **Approve simulated step** or **Reject simulated step** and confirm the message: **Nothing was sent.**
8. Refresh the tab and confirm that the investigation disappears.

## Safety model

Gemini is an optional literal-fact extraction assistant. Its output is untrusted. Deterministic Python validation controls:

- source-span and code-value integrity;
- supported code shapes and unique-pair expansion;
- payer/program, date, modifier, same-date, and same-claim gates;
- reference provenance, checksum, scope, effective period, verification, and licence metadata;
- final result labels;
- request-size, pair, and rate limits; and
- whether a result may be presented as a potential discrepancy.

AI cannot declare that a bill is wrong. Uncertain extraction or applicability fails closed. The approval control changes only the JavaScript object held by the current page; it performs no fetch, navigation, copy, download, publication, message, or external action.

## Reference-data limitation

The checked-in `billwatch/reference_bootstrap.py` data is a small illustrative snapshot. Its NCCI relationship is explicitly unverified, so the public app returns `REFERENCE_UNVERIFIED` and cannot use it to produce a potential discrepancy.

The repository also contains a fail-closed importer and checksum-verified read-only SQLite repository for reference files a user legally obtained. They are not connected to the public app. Protected CMS or AMA data must not be downloaded, imported, or published without an appropriate licence.

## Repository layout

- `app.py` — public inline HTML/CSS/JavaScript interface and JSON API.
- `billwatch/arbitrary_analysis.py` — ordinary arbitrary-input extraction and bounded pair analysis.
- `billwatch/synthetic_demo.py` — the isolated author-written public demo rule.
- `billwatch/llm_schemas.py` — strict AI-output validation.
- `billwatch/reference_data.py` — immutable, versioned, fail-closed reference store.
- `billwatch/pipeline.py` — deeper internal pipeline that is not presented as the public workflow.
- `tests/` — deterministic unit, API, UI-contract, and safety tests.
- `docs/hackathon-build/` — approved scope, PRD, technical spec, checklist, and evidence notes.

## Installation and local use

Python 3.11 or newer is recommended.

```text
python -m pip install -r requirements-dev.txt
```

`GEMINI_API_KEY` is optional. Without it, the ordinary app uses a deterministic input-driven offline extractor and does not pretend Gemini ran.

Linux, macOS, or Termux:

```text
export GEMINI_API_KEY='your-key'   # optional
PORT=8091 python app.py
```

Windows PowerShell:

```text
$env:GEMINI_API_KEY = 'your-key'   # optional
$env:PORT = '8091'
python app.py
```

Open `http://127.0.0.1:8091/`.

## API

Investigations use `POST /investigate`. `GET /investigate` intentionally returns HTTP 405.

```json
{
  "bill_text": "CPT 99213 Office visit $180.00",
  "payer_scope": "unknown",
  "service_date": null,
  "modifiers": [],
  "same_date_confirmed": null,
  "same_beneficiary_confirmed": null,
  "claim_status": null
}
```

The backward-compatible response includes facts, findings, status, missing context, a request ID, operating mode, and reference provenance where a lookup occurred. Optional hackathon fields describe completed stages and resumable context.

## Verification evidence

Final local results:

- `unittest`: 533 tests passed in 2.241 seconds; baseline was 488.
- `pytest`: 533 tests plus 24 subtests passed in 5.60 seconds; baseline was 488 tests plus 10 subtests.
- focused synthetic module: 12 passed.
- synthetic/analyzer/API isolation group: 42 passed.
- analyzer/API/state-machine group: 40 passed.

Public revision checks passed for `/health`, `/`, POST-only investigation, ordinary no-match wording, unverified-reference blocking, isolated synthetic pause/resume, distinct request IDs, retained Attempt 1, simulated approval with no navigation or new tab, and refresh clearing. A synthetic privacy marker produced zero Cloud Logging matches, and the deployed revision produced zero error-level log entries during verification.

Docker was not installed on the Windows build host, so a separate local Docker run was unavailable. Google Cloud built the unchanged Dockerfile successfully when creating the verified public revision.

## Known proof-of-concept limitations

- Investigation history is lost on refresh or tab close.
- There are no user accounts, durable sessions, or server-side case records.
- The public reference snapshot is illustrative and not current official NCCI data.
- Approval is simulated and cannot send or publish anything.
- The proof of concept is not a production compliance solution for protected health information.
- A production release would require a formal privacy, security, licensing, accessibility, reliability, and cost review.

## License

No open-source licence is currently included. Unless the owner adds one, treat the repository as all rights reserved.
