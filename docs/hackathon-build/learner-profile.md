# Learner Profile

## Participant

- Name: Macdonald Bereiweriso
- Background: Complete beginner and non-coder. Built the existing application with Claude's help; has used Termux on Android to copy and run commands, Python to start the application and run tests, GitHub for the repository, and Codex on Windows.
- What brought them to the hackathon: Not solicited during onboarding

## Project Idea

- Initial idea (or "exploring"): Strengthen the existing tested application, BillWatch, into a credible Taskmaster workflow for evidence-grounded medical-bill investigation. It should accept arbitrary medical-bill text; extract codes, dates, amounts, and exact source evidence; evaluate every unique code pair against versioned reference data; identify missing context; request missing information; route uncertain or consequential findings for human approval; and produce an auditable, safe next-action summary. Scope is medical bills only, not general utility, rent, or telephone bills. It must fail closed, avoid unsupported medical, legal, or insurance claims, use only synthetic or properly licensed data, and preserve existing tests.

## Confirmed Product Direction

- Input: pasted itemized medical-bill text or a supported TXT, CSV, or JSON file, with optional payer/program, service date, modifiers, claim/EOB status, and same-date/same-beneficiary-or-claim confirmation.
- Core workflow: validate input; create an investigation ID; extract supported facts with exact source spans; plan the investigation; evaluate every unique supported code pair; select bounded references by payer and service date; validate provenance, effective dates, licence metadata, checksum, and scope; record every stage; pause when required; resume after human correction or confirmation without losing the audit trail.
- Pause conditions: missing or uncertain required context; unproven payer/date/beneficiary/claim/modifier setting; unverified, unlicensed, out-of-period, or inapplicable references; and any consequential external action.
- Final report: overall status; source-cited facts; every pair finding; missing or uncertain context; reference source/version/effective date/retrieval date/verification/licence basis; completed stages; human decisions; and a safe proposed next step.
- Allowed result language: potential discrepancy, insufficient context, reference unverified, no matching rule, or no supported discrepancy found. A code-pair match alone must never become a claim that a bill is definitely incorrect.
- Autonomy boundary: deterministic gates may produce provisional evidence-grounded findings and draft safe next steps. Human approval is required for uncertain facts, unproven context, consequential conclusions, appeals or communications, provider/payer contact, payment decisions, sensitive-data handling, and data without an established licence. The proof of concept sends nothing externally.
- Hackathon proof: demonstrate ingestion, exact source-grounded extraction, investigation planning, complete pair evaluation, bounded/versioned evidence lookup, missing or conflicting context detection, a human checkpoint, correction or confirmation, resumed analysis, and an auditable final report.
- Required demo cases: a missing-context pause; a no-matching-rule result; a clearly synthetic case that legitimately reaches potential discrepancy; proof that unverified evidence cannot support a discrepancy; and proof that external action cannot bypass approval.

## Technical Experience

- Experience level: Complete beginner; cannot independently write or safely review code.
- Languages/frameworks known: No independent language or framework proficiency. Has operational experience running a Python application and its tests.
- AI coding tools used before: Claude and Codex.
- Prior experience planning before coding: Not yet established; the existing application was built with Claude's assistance.

## Build Preferences

- Total implementation budget: 10 hours, including implementation, testing, deployment, and demo preparation.
- Preferred pace: Small, carefully explained steps.
- Likely support needs: Plain-language explanations, safety backups, explicit inspection before modification, and tests before and after every important change.
- Notes for downstream commands: Never assume technical terminology is understood. Inspect the existing application before proposing changes. Preserve working behavior and tests; do not replace or rebuild working parts without evidence that it is necessary. Emphasize reversible changes, safety boundaries, and human approval for uncertain or consequential findings. Preserve arbitrary medical-bill input, exact evidence spans, deterministic gates, separation of model proposals from deterministic decisions, reference provenance/licence safeguards, evidence models and legal state transitions, privacy and no bill-content logging/storage, offline operation, request/rate/pair limits, POST /investigate safety, and all existing tests.
- Scope priorities: (1) real pause, human correction or confirmation, and resume; (2) concise evidence and investigation-stage timeline; (3) visible approval gate for a simulated external action. No real appeal, message, payment, or external sending.
- Session model: browser-session-only state. Raw bill text must not be persisted on the server or outside the active browser session. Losing progress when the tab closes is acceptable and must be documented as a proof-of-concept limitation.

## Design Preferences

- Overall feeling: a calm consumer advocate's office combined with a meticulous evidence laboratory—reassuring, trustworthy, and methodical rather than frightening or overly clinical.
- Visual foundation: preserve the existing dark navy foundation; use restrained blue and teal accents, strong contrast, readable typography, generous spacing, and clear evidence cards.
- Avoid visually: excessive red, flashing warnings, crowded dashboards, decorative medical imagery, alarming symbols, and presentation that implies a definitive medical conclusion.
- Written voice: combine a calm guide with a neutral investigator; explain findings in plain language while remaining explicit and careful about uncertainty.
- Demo emphasis: make the missing-context pause and resume the emotional center, supported by a visible evidence trail. This should demonstrate genuine agentic behavior under human control.
- Avoid in copy: "fraud," "illegal," "definitely wrong," "guaranteed error," pressure to dispute or withhold payment, and any similarly conclusive language not independently established. The proof of concept should never make those claims.
