# Product Requirements Document

## Product Summary

BillWatch is a calm, evidence-grounded assistant for investigating arbitrary itemized medical bills. It accepts pasted bill text or a supported TXT, CSV, or JSON file; identifies supported billing codes, dates, amounts, and other literal facts with exact source evidence; plans and performs bounded code-pair checks; and explains what the available evidence does and does not support.

The proof of concept is designed to demonstrate controlled agency rather than unchecked automation. BillWatch may perform safe, deterministic investigation work on its own, but it must pause when required context is missing, refuse to turn unverified evidence into a consequential finding, and keep a person in control of any proposed external action. The central demonstration is a real pause, human correction or confirmation, and resumed investigation with the earlier attempt preserved in a visible audit timeline.

BillWatch is not a medical, legal, insurance, coding, or payment adviser. It does not determine that a bill is fraudulent, illegal, definitely wrong, or guaranteed to contain an error. It does not send appeals, messages, documents, payments, or any other external communication.

## Product Goal

Within a ten-hour implementation budget, strengthen the existing working BillWatch application so a hackathon reviewer can see all of the following in one coherent browser experience:

1. BillWatch receives arbitrary supported medical-bill text rather than relying on two predetermined real billing codes.
2. The investigation shows exact source-grounded facts and only the stages that genuinely occurred.
3. Missing context causes a visible pause instead of a guess.
4. A person can supply or confirm permitted context and resume the same investigation.
5. The resumed report retains the earlier attempt and the human decision in its audit trail.
6. Verified, clearly synthetic evidence can support the bounded label `POTENTIAL_DISCREPANCY` when every required gate passes.
7. Unverified evidence cannot support that label.
8. A simulated external-action approval choice is visible only after `POTENTIAL_DISCREPANCY`, and nothing is sent even when the user approves it.

## Target User

The primary user is a person reviewing an itemized medical bill who wants a careful explanation of possible billing-code relationships without needing to understand billing terminology or reference-data mechanics.

The user needs:

- plain-language guidance;
- exact evidence from the text they supplied;
- a visible explanation of missing or uncertain context;
- cautious result language that distinguishes a review signal from proof of an error;
- a clear record of what BillWatch did automatically and what a person confirmed;
- confidence that the proof of concept did not store their bill on the server or send anything externally.

The primary hackathon viewer is also a user of the demo. They need to understand within a few minutes why the pause is useful, why the resumed result is auditable, why the synthetic rule is not official billing data, and why the approval control is a safe simulation rather than a working external-action system.

## Product Experience Principles

### Calm and methodical

BillWatch should feel like a calm consumer advocate's office combined with a meticulous evidence laboratory. The experience should be reassuring and precise, not frightening, accusatory, or overly clinical.

### Evidence before conclusions

Every supported extracted fact must remain connected to the exact bill text that supports it. Results must explain the evidence boundary and must not imply that a code-pair match proves a bill is incorrect.

### Pause instead of guess

When required, user-suppliable context is missing or uncertain, BillWatch must stop at a visible checkpoint, explain why the information matters, and wait for the user. It must not silently fill in payer, date, claim relationship, modifier, or other applicability facts.

### Human control over consequential action

Automatic work may end in a provisional, evidence-grounded result. It must not produce an external consequence. Any approval control in this proof of concept is explicitly simulated and records only a browser-local choice.

### Honest workflow visibility

The stage timeline must describe only work that actually occurred in the public workflow. It must not present the deeper internal pipeline as connected, imply that a failed stage completed, or describe a simulated control as a real external integration.

### Privacy made visible

The first screen must clearly explain that investigation progress exists only for the active browser session, that the server does not persist raw bill text, and that closing the tab can remove progress. This limitation should be understandable before the user submits a bill.

## Result Language And Meanings

The product may use the following bounded result concepts. Each result must include plain-language meaning and a safe next step.

### Potential discrepancy

`POTENTIAL_DISCREPANCY` means that every deterministic applicability gate required by the isolated, verified reference passed and that the relationship deserves human review. It does not mean the bill is definitely incorrect. Only this result may reveal the simulated proposed-action approval card.

### Insufficient context

`INSUFFICIENT_CONTEXT` means BillWatch cannot safely establish applicability from the current bill and supplied context. If the missing information is one of the permitted context fields, the experience becomes a pause with guided controls and **Resume investigation**. If the limitation cannot be resolved through those controls, the report explains that BillWatch cannot continue with the available information and does not offer a misleading resume path.

### Reference unverified

`REFERENCE_UNVERIFIED` means a possible relationship was found in evidence that is not verified, licensed for the intended use, within its effective period, or otherwise established as applicable. The report must identify the reference and the failed trust boundary. It must not produce `POTENTIAL_DISCREPANCY`, must not ask the user to approve an external action, and must not imply that supplying ordinary bill context can repair the reference.

### No matching rule

`NO_MATCHING_RULE` means none of the bounded references loaded for this proof of concept matched the supported code pair. It does not mean the bill is error-free or that no other rule exists.

### No supported discrepancy found

`NO_SUPPORTED_DISCREPANCY_FOUND` means the completed checks did not establish a supported potential discrepancy in the bounded references and context available to BillWatch. It must not be phrased as a clean-bill guarantee.

## Core User Journey

1. The user opens the existing BillWatch page and sees the familiar dark-navy investigation form, the safety disclaimer, and a prominent browser-session privacy notice.
2. The user either pastes arbitrary itemized medical-bill text, selects a supported TXT, CSV, or JSON file, or deliberately chooses the separate **Hackathon Demo** card.
3. The user may supply existing context fields, including payer/program, service date, modifiers, claim or EOB status, same-date confirmation, and same-beneficiary-or-claim confirmation.
4. BillWatch validates the input. Empty, unsupported, oversized, or otherwise invalid input receives a clear correction message and produces no investigation result.
5. For valid input, BillWatch creates an investigation identifier and begins a visible investigation attempt.
6. BillWatch extracts supported facts with exact source evidence, identifies supported codes, deduplicates them, creates every unique pair within existing limits, plans the applicable checks, and evaluates the pairs against bounded references.
7. The timeline records only the stages that actually occurred. Extracted evidence remains inspectable throughout the experience.
8. If required, user-suppliable context is missing, BillWatch pauses. It keeps the evidence visible, explains only the missing items and why each matters, and presents only the relevant existing context controls.
9. The original bill text is locked during the paused investigation. If an extracted code or source fact is wrong, the user is told to start a new investigation and correct the original text rather than editing evidence in place.
10. The user supplies or confirms context and chooses **Resume investigation**.
11. BillWatch records the human confirmation, safely reruns the analysis with the browser-held bill text and updated context, and adds the new attempt to the same investigation timeline.
12. The newest report becomes the primary result. The first attempt remains available in a compact, expandable timeline.
13. The final report shows its bounded status, exact evidence, every code-pair finding, missing or uncertain context, reference metadata, completed stages, human decisions, and a safe proposed next step.
14. Only when the status is `POTENTIAL_DISCREPANCY` does BillWatch reveal a simulated proposed-action approval card. **Approve** or **Reject** records a browser-local decision and states that nothing was sent.
15. Starting a new investigation or loading the synthetic demo while an investigation exists asks for confirmation before clearing the current browser timeline.

## Epics And User Stories

### Epic 1: Understand The Safety And Session Boundary

#### Story 1.1: First-screen orientation

As a person reviewing a bill, I want to understand what BillWatch can and cannot do before I submit information so that I can make an informed choice about using it.

Acceptance criteria:

- The existing dark-navy bill form remains the primary first-screen experience rather than being replaced by a new dashboard.
- A clear notice near the form says that this proof of concept keeps investigation progress only in the active browser session and does not provide durable account or server history.
- The notice explains that closing the tab can clear the investigation and that the user should save any information they need before leaving.
- The existing safety disclaimer remains visible and says that BillWatch provides evidence-grounded review support, not medical, legal, insurance, coding, or payment advice.
- The page does not promise that a bill can be proven correct or incorrect.
- The page does not pressure the user to dispute a charge, withhold payment, or contact a provider or payer.

#### Story 1.2: Visible privacy expectation

As a privacy-conscious user, I want to know where my bill information goes so that I do not mistake a demonstration for a persistent service.

Acceptance criteria:

- The product states that raw bill text is processed transiently and is not persisted or logged by the server.
- The product states that the active browser session holds the information needed for pause and resume.
- No user-facing screen offers an account, saved-history page, cloud sync, cross-device resume, or server-side retrieval.
- Ending the active tab session does not leave a product feature through which the prior raw bill or timeline can be retrieved.

### Epic 2: Submit An Arbitrary Supported Medical Bill

#### Story 2.1: Paste or load supported text

As a user with an itemized medical bill, I want to paste its text or choose a supported text-based file so that I can investigate more than a predetermined example.

Acceptance criteria:

- The form accepts pasted medical-bill text.
- The form accepts the application's supported TXT, CSV, and JSON file paths without adding PDF, image, OCR, or handwriting promises.
- The form exposes the existing optional context fields without requiring the user to understand reference rules.
- A valid arbitrary bill is not required to contain the synthetic demo identifiers.
- Existing request, size, rate, and pair-expansion limits remain visible through clear error messages when reached.
- The investigation uses a submission action and does not place bill content into a shareable page address.

#### Story 2.2: Correct invalid input safely

As a user who submits empty or invalid information, I want a specific correction message so that I can fix the problem without mistaking it for an investigation finding.

Acceptance criteria:

- Empty input produces a plain-language message explaining that bill text is required.
- An unsupported file type identifies the supported TXT, CSV, and JSON choices.
- Malformed, oversized, or limit-exceeding input identifies the condition in non-technical language where possible.
- The user's still-safe browser input remains visible for correction whenever the application can retain it.
- Invalid input creates no result report, no code-pair finding, and no completed investigation timeline.
- Validation errors are visually distinct from medical-bill findings and do not use alarming language.

### Epic 3: Keep The Synthetic Demonstration Separate

#### Story 3.1: Deliberately enter the demo path

As a hackathon viewer, I want a clearly labelled synthetic example so that I can reproduce the complete workflow without confusing demonstration data with real billing data.

Acceptance criteria:

- A separate, prominent **Hackathon Demo** card is visually distinct from the ordinary bill form.
- The card explicitly says that its contents and rule are author-written and synthetic.
- The card says that `BW-DEMO-001` and `BW-DEMO-002` are demonstration identifiers, not CPT or HCPCS codes and not CMS, AMA, insurer, payer, or clinical data.
- Loading the demo is an intentional user action; the ordinary arbitrary-bill workflow does not silently substitute the synthetic example.
- If an investigation timeline already exists, loading the demo asks for confirmation before clearing it.
- The synthetic example begins with at least one required context item absent so it reliably demonstrates the pause and resume journey.

#### Story 3.2: Display the isolated synthetic rule honestly

As a viewer assessing trustworthiness, I want to inspect the synthetic rule's identity and provenance so that I can see why it may pass the proof-of-concept gates without mistaking it for official evidence.

Acceptance criteria:

- Exactly one author-written synthetic rule is available to the public demo path.
- Its presentation is separate from the existing illustrative, unverified NCCI fixture.
- Its evidence card shows a synthetic source name, version, effective dates, retrieval date, verification status, licence basis, scope, and integrity information such as a checksum.
- Every synthetic label remains visible on the pause screen, resumed report, and evidence detail where the rule appears.
- The synthetic rule can produce `POTENTIAL_DISCREPANCY` only after all its required context and trust gates pass.
- The product never implies that the synthetic relationship applies to a real bill.

### Epic 4: See Source-Grounded Evidence And A Real Investigation Plan

#### Story 4.1: Inspect extracted facts

As a user, I want each extracted fact tied to the text that supports it so that I can check what BillWatch actually observed.

Acceptance criteria:

- Every displayed supported code, date, amount, or other literal fact includes the exact source excerpt or span used as evidence.
- A code is not presented as source-supported unless its value appears in the cited span.
- Unsupported model suggestions do not appear as confirmed facts.
- Offline deterministic extraction remains a valid way to complete the public workflow.
- Evidence remains visible when the investigation pauses and after it resumes.
- The UI distinguishes extracted source facts from user-supplied or user-confirmed context.

#### Story 4.2: Understand what BillWatch plans to check

As a user, I want a concise investigation plan so that the automated work is understandable rather than hidden behind one result label.

Acceptance criteria:

- The report identifies the supported codes considered.
- Duplicate code values do not create duplicate pair findings.
- Every unique supported pair within the existing safety limit receives a visible result entry.
- The plan identifies the types of applicability context BillWatch considered, such as payer/program, service date, same-date relationship, same beneficiary or claim, modifiers, and claim status when relevant.
- The plan does not list deeper pipeline stages that the public workflow did not execute.
- If a limit prevents additional pair expansion, the report says that the analysis was bounded rather than implying every imaginable relationship was checked.

#### Story 4.3: Inspect bounded reference evidence

As a user, I want to see which reference was checked and why it could or could not be used so that the finding is auditable.

Acceptance criteria:

- Each matching or potentially relevant reference card shows source, version, effective period, retrieval date, verification status, licence basis, scope, and integrity metadata available to the product.
- The report explains whether payer/program and service date fall inside the reference's supported scope.
- Evidence that is unverified, unlicensed, outside its effective period, or inapplicable cannot produce `POTENTIAL_DISCREPANCY`.
- The existing illustrative NCCI relationship remains visibly unverified and produces `REFERENCE_UNVERIFIED` rather than a discrepancy label.
- Protected or user-licensed data is not downloaded, republished, or presented as bundled official data by this proof of concept.

### Epic 5: Follow A Truthful Investigation Timeline

#### Story 5.1: See stages as they occur

As a user, I want a concise ordered timeline so that I can distinguish completed work, a pause, a human decision, and resumed work.

Acceptance criteria:

- A valid investigation receives an investigation identifier visible in the report or timeline.
- Candidate events include bill received, facts extracted, pairs generated, references checked, context evaluated, investigation paused, human context supplied, analysis resumed, final result produced, and simulated approval decision recorded.
- An event appears only when the corresponding action genuinely occurred.
- The timeline distinguishes automatic BillWatch events from human decisions.
- Paused, completed, and failed states are visually distinguishable without flashing, excessive red, or alarming symbols.
- The timeline is concise by default and allows older attempt detail to remain available without crowding the main result.

#### Story 5.2: Preserve attempts within the active investigation

As a user who resumes an investigation, I want the earlier attempt preserved so that the final result does not erase why human input was needed.

Acceptance criteria:

- The first paused attempt remains in a compact, expandable portion of the active browser timeline.
- The human-supplied or confirmed context is recorded as a human event without rewriting the earlier attempt.
- The resumed analysis is recorded as a new attempt under the same investigation journey.
- The newest report is displayed as the primary report after resume.
- The product does not claim durable history beyond the active browser-session boundary.

### Epic 6: Pause For Missing Context

#### Story 6.1: Ask only for information that matters now

As a user facing an uncertain investigation, I want BillWatch to ask only for the missing context so that I can respond without repeating information it already has.

Acceptance criteria:

- A user-suppliable missing context gate produces a visible pause rather than a speculative result.
- Extracted evidence and completed stage history remain visible during the pause.
- The pause panel lists only the unresolved supported context fields.
- Each requested item includes a short plain-language explanation of why it matters to applicability.
- The panel presents only the relevant existing controls for payer/program, service date, modifiers, claim/EOB status, same-date confirmation, or same-beneficiary-or-claim confirmation.
- The primary continuation action is labelled **Resume investigation**.
- No simulated external-action approval card appears on the pause screen.

#### Story 6.2: Protect source evidence during a pause

As a user, I want the original source to remain stable while I confirm context so that the audit trail remains trustworthy.

Acceptance criteria:

- Original bill text is locked while the current investigation is paused.
- The user can change only the supported context controls within the pause/resume workflow.
- If the user says an extracted code or exact source fact is wrong, the interface explains that they must start a new investigation and correct the original bill text.
- Starting that new investigation asks for confirmation before clearing the current timeline.
- No in-place evidence edit silently changes the first attempt.

### Epic 7: Resume After Human Confirmation

#### Story 7.1: Continue the same investigation safely

As a user who supplies missing context, I want BillWatch to resume the investigation without losing its earlier evidence so that I can see the effect of my confirmation.

Acceptance criteria:

- **Resume investigation** is available only when the required visible controls contain acceptable values.
- Choosing Resume records which supported context was supplied or confirmed by a person.
- BillWatch safely reruns the analysis using the same browser-held bill source and the updated context.
- The resumed analysis does not reuse a stale final status without re-evaluating applicable gates.
- The first attempt, pause reason, human event, and second attempt remain ordered in the timeline.
- The final report identifies user-confirmed context separately from source-extracted facts.

#### Story 7.2: Prevent duplicate or out-of-order actions

As a user, I want clear processing feedback so that repeated clicks do not create misleading duplicate investigations.

Acceptance criteria:

- While an Analyze or Resume action is in progress, the triggering control cannot be repeatedly activated.
- The screen indicates that the investigation is in progress without inventing completed stages.
- A second Resume event cannot appear before the first resumed analysis has resolved.
- If the active investigation is no longer in a resumable state, the product does not show an enabled Resume control.

### Epic 8: Receive A Cautious, Auditable Report

#### Story 8.1: Understand the overall result

As a user, I want the report to explain its status in plain language so that I do not overinterpret a billing-rule check.

Acceptance criteria:

- The newest report presents one clear overall bounded status.
- The report explains what that status establishes and what it does not establish.
- `POTENTIAL_DISCREPANCY` is described as a review signal supported by the verified bounded rule and confirmed context, not proof that the bill is wrong.
- `REFERENCE_UNVERIFIED` identifies the failed evidence boundary and cannot be visually mistaken for a supported discrepancy.
- `NO_MATCHING_RULE` says that no rule matched in the loaded bounded sources and does not claim no rule exists elsewhere.
- `NO_SUPPORTED_DISCREPANCY_FOUND` does not claim that the bill is correct, clean, or free of errors.
- `INSUFFICIENT_CONTEXT` either leads to the permitted guided pause or explains why the available workflow cannot safely continue.

#### Story 8.2: Review every pair and the supporting context

As a user, I want a complete pair-by-pair account so that one highlighted pair does not hide the rest of the bounded investigation.

Acceptance criteria:

- Every unique supported pair considered by the analyzer has a visible finding.
- Each pair entry identifies its status, relevant context, and matching or non-matching bounded reference outcome.
- Missing, uncertain, or conflicting context is shown alongside the affected finding.
- Reference metadata is available without requiring the user to infer provenance from a rule name.
- The report includes a safe proposed next step that matches the status and avoids instructing the user to dispute, contact, pay, or withhold payment automatically.

### Epic 9: Demonstrate A Non-Sending Approval Boundary

#### Story 9.1: Reveal approval only when warranted

As a hackathon viewer, I want the proposed-action boundary to appear only after a fully gated synthetic result so that human approval is shown as a consequence of evidence, not decoration.

Acceptance criteria:

- Only a final `POTENTIAL_DISCREPANCY` report displays the simulated proposed-action approval card.
- Missing-context, no-match, no-supported-discrepancy, and unverified-reference results never display the card.
- The card states that the proposed action is simulated and that this proof of concept cannot send an appeal, message, document, complaint, payment, or provider/payer contact.
- The proposed action uses careful review language and does not claim the bill is wrong.
- The card does not appear before the final deterministic result is available.

#### Story 9.2: Record approve or reject without acting externally

As a user, I want to approve or reject the simulated proposal so that the audit trail demonstrates human control without causing a real-world action.

Acceptance criteria:

- The user can choose **Approve** or **Reject** once the card is available.
- Either choice records a clearly labelled human decision in the active browser timeline.
- After either choice, the screen explicitly says that nothing was sent.
- Approval does not create, send, store, publish, or transmit an appeal, message, document, complaint, payment instruction, or contact request.
- Rejection does not alter or erase the evidence-grounded investigation report.
- The choice is not presented as durable outside the active browser session.

### Epic 10: Recover Honestly From Errors Or Reset The Session

#### Story 10.1: Retry a failed analysis

As a user whose analysis fails, I want to keep my input and try again so that a temporary failure does not look like a medical-bill finding.

Acceptance criteria:

- If analysis fails after valid submission, the user's browser-held input remains visible when safely possible.
- The screen provides a clear **Retry** action.
- The error says the investigation did not finish and avoids presenting a partial result as final.
- No unfinished stage is marked complete.
- A failed reference lookup, extraction, or report step does not silently become a no-match or no-discrepancy result.
- Retrying creates a truthful new attempt or continuation in the active timeline without rewriting the failed event as a success.

#### Story 10.2: Start over intentionally

As a user, I want to start another investigation without accidentally erasing the current audit trail.

Acceptance criteria:

- **Start new investigation** is available from paused and final states.
- If the current browser timeline contains investigation activity, the product asks for confirmation before clearing it.
- Loading the synthetic demo while activity exists uses the same confirmation boundary.
- Cancelling the confirmation leaves the current bill, report, and timeline unchanged.
- Confirming clears the current browser investigation state, unlocks the bill input, and returns to a clean first-run form.
- Clearing the browser investigation does not trigger a server delete claim, because the proof of concept does not persist a server-side investigation record.

## First-Run, Empty, Error, And Out-Of-Order States

### First run

- Show the ordinary bill form, safety disclaimer, browser-session notice, and separate Hackathon Demo card.
- Show no fabricated investigation identifier, report, completed stage, or approval card.
- Use a calm empty state that tells the user what supported input they can provide.

### Empty or invalid submission

- Keep the user at the input step.
- Identify what must be corrected.
- Produce no investigation result, pair findings, or completed timeline.

### Valid investigation with user-suppliable missing context

- Show completed evidence and stages.
- Mark the investigation paused.
- Ask only for missing permitted fields and explain why each matters.
- Lock the original bill text and offer Resume or Start new investigation.

### Context cannot repair the limitation

- Show a cautious bounded report, such as reference unverified or insufficient applicable evidence.
- Explain the specific boundary.
- Do not offer a misleading Resume control if none of the permitted context fields can resolve it.
- Do not show the simulated approval card.

### Analysis failure

- Preserve browser input when safe.
- Mark no unfinished stage as successful.
- Offer Retry and Start new investigation.
- Do not convert the failure into a bill finding.

### Repeated action while processing

- Prevent duplicate Analyze or Resume actions.
- Show in-progress state only for work genuinely underway.
- Add one truthful outcome per completed attempt.

### Attempt to load demo or start over during an active investigation

- Ask for confirmation before clearing the active browser timeline.
- If cancelled, make no change.
- If confirmed, clear active investigation state and begin the requested clean path.

### Tab closes or browser session ends

- Treat the prior progress as intentionally non-durable.
- Do not offer server retrieval or imply that an account history exists.
- Keep this limitation visible enough that loss of progress is not a surprise.

## Visual And Written Requirements

- Preserve the existing dark-navy foundation.
- Use restrained blue and teal accents, strong contrast, readable typography, generous spacing, and clear evidence cards.
- Make the missing-context pause and Resume action the visual and emotional center of the main demo.
- Keep the evidence and stage timeline concise rather than creating a crowded dashboard.
- Use expandable detail for the first attempt and detailed metadata where that reduces clutter without hiding the audit trail.
- Avoid excessive red, flashing warnings, decorative medical imagery, alarming symbols, and visual treatment that implies a diagnosis or proven violation.
- Use a calm-guide and neutral-investigator voice.
- Avoid “fraud,” “illegal,” “definitely wrong,” “guaranteed error,” and equivalent unsupported conclusions.
- Avoid language that pressures the user to dispute a bill, contact a party, make or stop a payment, or take any other consequential step.
- Explain billing and reference concepts in plain language before or alongside technical labels.

## What We Are Building

The ten-hour proof of concept includes:

- the existing arbitrary medical-bill form and TXT, CSV, and JSON support;
- a prominent browser-session and privacy notice;
- a separate, clearly labelled Hackathon Demo card;
- one isolated author-written synthetic verified rule using unmistakably synthetic identifiers;
- exact source-evidence display;
- a concise, truthful investigation-stage timeline;
- a real missing-context pause for supported existing context fields;
- locked source text during the active paused investigation;
- human confirmation or correction of permitted context;
- safe resumed analysis with the first attempt retained;
- bounded final result presentation and reference metadata;
- a simulated, browser-local approve/reject card only after `POTENTIAL_DISCREPANCY`;
- clear invalid-input, retry, reset-confirmation, and non-durable-session behavior;
- focused proof that unverified evidence cannot produce a discrepancy and that no external action is sent.

If implementation time becomes tight, work is protected in this order:

1. Pause, human correction or confirmation, and resume.
2. Evidence and genuine-stage timeline.
3. Simulated approval boundary.

The existing analyzer, safety gates, privacy guarantees, request limits, offline path, and regression behavior have priority over visual polish or optional detail.

## What We Would Add With More Time

These items are explicitly deferred because they would dilute the ten-hour demonstration or introduce data, licensing, security, and operational risks:

- official NCCI acquisition, import, refresh, or public distribution;
- connection of the existing read-only SQLite repository to the public workflow;
- the full deeper internal pipeline as the public end-to-end workflow;
- user accounts, authentication, a database, durable server history, cross-device resume, or multi-user sessions;
- PDF or image input, OCR, handwriting recognition, or broader document formats;
- in-place correction of extracted codes or exact evidence spans;
- production-grade sensitive-data storage, sharing, publication, or compliance claims;
- real appeal drafting or sending;
- real messages, complaints, documents, provider or payer contact, payments, or other external actions;
- broad payer coverage or use of protected CMS, AMA, insurer, payer, or clinical data without an established licence;
- a broad redesign, new frontend framework, unrelated refactoring, or replacement of working analysis components;
- claims that BillWatch provides medical, legal, insurance, coding, or payment advice.

## Submission Proof Points

The completed product should make the following evidence easy to capture in the live demo, screenshots, test notes, and Devpost write-up:

1. **Arbitrary input:** submit a supported medical-bill example that is not the synthetic demo and show exact extracted source evidence and all unique bounded pair findings.
2. **Agentic pause:** load the clearly labelled synthetic demo with context intentionally missing and show BillWatch stop rather than guess.
3. **Human control:** supply or confirm the requested context and select **Resume investigation**.
4. **Audit continuity:** show the first attempt, pause reason, human decision, resumed attempt, and newest report in one investigation timeline.
5. **Verified synthetic path:** show `BW-DEMO-001` and `BW-DEMO-002`, their unmistakable synthetic labels and provenance, and the fully gated `POTENTIAL_DISCREPANCY` result.
6. **Unverified evidence block:** run the illustrative unverified NCCI case and show `REFERENCE_UNVERIFIED`, with no discrepancy label and no approval card.
7. **No-match caution:** show a no-matching-rule or no-supported-discrepancy result that does not claim the bill is error-free.
8. **Approval boundary:** show the simulated approval card only after the synthetic potential discrepancy, choose Approve or Reject, and show the timeline record plus the statement that nothing was sent.
9. **Failure honesty:** demonstrate or test that invalid input creates no result and that an analysis failure never marks unfinished stages complete.
10. **Privacy boundary:** show the browser-session notice and document that raw bill text is not persisted or logged on the server and that progress can be lost when the tab closes.

## Product Acceptance Summary

BillWatch is ready for this hackathon proof of concept when a reviewer can complete the main synthetic pause-and-resume story, inspect exact evidence and genuine stages, understand every bounded result, see an unverified reference fail closed, and verify that the visible approval control sends nothing. The experience must preserve existing working behavior and safety constraints while remaining small enough to implement, test, deploy, and rehearse within ten hours.
