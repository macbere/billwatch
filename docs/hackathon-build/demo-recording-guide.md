# BillWatch Four-Minute Demo Recording Guide

## What you need

- The public app: https://billwatch-403260979598.us-central1.run.app
- The architecture diagram: `output/pdf/billwatch-hackathon-architecture.pdf`
- A quiet room and, if available, earphones with a microphone.
- About ten minutes for one practice run and one real recording.

Use only BillWatch's built-in synthetic or illustrative examples. Do not show a real medical bill, API key, password, private notification, unrelated browser tab, or Cloud Console secret.

## Record on Windows

1. Close unrelated windows and silence notifications.
2. Open the public app in one tab and the architecture PDF in another.
3. Press **Windows + Shift + R** to open Snipping Tool's video recorder.
4. Select the browser area, choose **Start**, and follow the script below.
5. Choose **Stop** when finished, then save the video with a clear name such as `billwatch-demo.mp4`.
6. If your recording has no microphone audio, use **Edit in Clipchamp** to add narration or captions.

Microsoft's current instructions are here: https://support.microsoft.com/en-us/windows/apps/use-snipping-tool-to-capture-screenshots

## Recording target

Keep the submitted video under four minutes. Aim for approximately **3:40 to 3:50** so natural pauses cannot push the final recording beyond the limit.

Make these points unmistakable:

1. BillWatch performs the investigative heavy lifting autonomously.
2. Gemini 3.5 Flash through the Google GenAI SDK is part of the ordinary-input path.
3. The deployed backend is visibly running on Google Cloud Run.
4. Human input appears only when required evidence is genuinely missing or at the final simulated consequential-action boundary.

## Word-for-word demo script

### 0:00-0:20 - Problem and promise

**Show:** The BillWatch home screen.

**Say:**

> Medical bills contain codes, dates, amounts, and payer context that can be difficult to investigate. A confident answer can be harmful when the evidence is incomplete. BillWatch is an evidence-grounded Taskmaster that pauses instead of guessing. It provides review support, not medical, legal, insurance, coding, or payment advice.

### 0:20-0:45 - Architecture and Google Cloud proof

**Show:** The architecture PDF, then the public `.run.app` address in the browser.

**Say:**

> BillWatch runs on Google Cloud Run. Its ordinary-input path uses Gemini 3.5 Flash through the Google GenAI SDK to propose literal facts. BillWatch then validates exact evidence, expands every supported code pair, checks reference applicability, and controls the bounded result with deterministic Python. The guided synthetic demo is deterministic and isolated so the core safety workflow remains repeatable.

### 0:45-1:10 - Start the guided example

**Show:** Return to the app, point to **Active browser tab only**, then select **Load synthetic guided example** and **Analyze Bill**.

**Say:**

> Progress exists only in this active tab and disappears on refresh or close. This separate example uses two author-written demonstration identifiers. They are not CPT or HCPCS codes and are not CMS, AMA, insurer, payer, or clinical data.

### 1:10-1:40 - The central pause

**Show:** `INSUFFICIENT CONTEXT`, exact evidence, the timeline, and the three questions.

**Say:**

> BillWatch performed the investigation automatically until it reached evidence it is not allowed to invent. It extracted both identifiers with exact source evidence, checked the bounded synthetic reference, and stopped only for the missing service and claim context. The source is locked, and only stages that actually completed appear in the timeline.

### 1:40-2:10 - Human confirmation and resume

**Show:** Enter `2026-08-01`, select both confirmations, and choose **Resume investigation**.

**Say:**

> I will now provide the missing context. Resume creates a fresh server request rather than silently changing the first result. The timeline records my confirmation, Attempt 1 remains available, and the newest report becomes primary.

### 2:10-2:45 - Bounded result

**Show:** The retained Attempt 1, new request ID, reference metadata, and `POTENTIAL DISCREPANCY` card.

**Say:**

> Every deterministic gate for this author-written synthetic rule passed, so BillWatch presents a potential discrepancy for review. The report explicitly says this is not proof that any bill is incorrect. It also shows the reference version, effective date, verification state, and exact evidence.

### 2:45-3:05 - Human-control boundary

**Show:** Select **Approve simulated step**.

**Say:**

> This approval is deliberately simulated. It changes only this browser tab and clearly states that nothing was sent. BillWatch does not send an appeal, contact a provider or payer, publish data, or change a payment.

### 3:05-3:30 - Fail-closed proof

**Show:** Open a fresh tab, load the multi-code example, analyze it, and point to the `REFERENCE UNVERIFIED` pair card.

**Say:**

> The ordinary illustrative NCCI relationship is explicitly unverified. BillWatch blocks it from supporting a discrepancy and never displays the approval control. No matching rule is also reported cautiously rather than as proof that a bill is error-free.

### 3:30-3:45 - Close

**Show:** Return to the title or architecture diagram.

**Say:**

> BillWatch makes evidence, uncertainty, and human control visible parts of the workflow. The public Cloud Run service and reproducible tests are available through the links in the project entry.

## Upload and verify

1. Watch the saved video once from beginning to end.
2. Confirm that the public URL, pause, resume, bounded result, approval message, and unverified-reference proof are readable.
3. Sign in to YouTube Studio, choose **Create**, then **Upload videos**, and select the saved file.
4. Use a clear title such as **BillWatch - All Things Agentic Hackathon Demo**.
5. Set the final hackathon demo video to **Public** so its visibility is unambiguous for judging.
6. Copy the final video URL and send it to Codex for the last preparation pass.
7. Test the link in a signed-out or private browser window before using it in Devpost.

YouTube's current upload instructions are here: https://support.google.com/youtube/answer/57407
