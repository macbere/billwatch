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

## Word-for-word demo script

### 0:00-0:25 - Problem and promise

**Show:** The BillWatch home screen.

**Say:**

> Medical bills contain codes, dates, amounts, and payer context that can be difficult to investigate. A confident answer can be harmful when the evidence is incomplete. BillWatch is an evidence-grounded Taskmaster that pauses instead of guessing. It provides review support, not medical, legal, insurance, coding, or payment advice.

### 0:25-0:50 - Architecture and Google Cloud proof

**Show:** The architecture PDF, then the public `.run.app` address in the browser.

**Say:**

> BillWatch runs on Google Cloud Run. For ordinary bills, Gemini 3.5 Flash through the Google GenAI SDK may propose literal facts. Deterministic Python validates exact source evidence, evaluates every unique code pair, checks reference applicability, and controls the final status. The guided synthetic demo is deterministic and isolated from ordinary medical-bill analysis.

### 0:50-1:20 - Start the guided example

**Show:** Return to the app, point to **Active browser tab only**, then select **Load synthetic guided example** and **Analyze Bill**.

**Say:**

> Progress exists only in this active tab and disappears on refresh or close. This separate example uses two author-written demonstration identifiers. They are not CPT or HCPCS codes and are not CMS, AMA, insurer, payer, or clinical data.

### 1:20-2:00 - The central pause

**Show:** `INSUFFICIENT CONTEXT`, exact evidence, the timeline, and the three questions.

**Say:**

> BillWatch extracted both identifiers with exact source evidence, checked the bounded synthetic reference, and stopped. It needs a service date and confirmation that the items share the same date and beneficiary-or-claim context. The source is locked, and only stages that actually completed appear in the timeline.

### 2:00-2:40 - Human confirmation and resume

**Show:** Enter `2026-08-01`, select both confirmations, and choose **Resume investigation**.

**Say:**

> I will now provide the missing context. Resume creates a fresh server request rather than silently changing the first result. The timeline records my confirmation, Attempt 1 remains available, and the newest report becomes primary.

### 2:40-3:15 - Bounded result

**Show:** The retained Attempt 1, new request ID, reference metadata, and `POTENTIAL DISCREPANCY` card.

**Say:**

> Every deterministic gate for this author-written synthetic rule passed, so BillWatch presents a potential discrepancy for review. The report explicitly says this is not proof that any bill is incorrect. It also shows the reference version, effective date, verification state, and exact evidence.

### 3:15-3:35 - Human-control boundary

**Show:** Select **Approve simulated step**.

**Say:**

> This approval is deliberately simulated. It changes only this browser tab and clearly states that nothing was sent. BillWatch does not send an appeal, contact a provider or payer, publish data, or change a payment.

### 3:35-3:55 - Fail-closed proof

**Show:** Open a fresh tab, load the multi-code example, analyze it, and point to the `REFERENCE UNVERIFIED` pair card.

**Say:**

> The ordinary illustrative NCCI relationship is explicitly unverified. BillWatch blocks it from supporting a discrepancy and never displays the approval control. No matching rule is also reported cautiously rather than as proof that a bill is error-free.

### 3:55-4:05 - Close

**Show:** Return to the title or architecture diagram.

**Say:**

> BillWatch makes evidence, uncertainty, and human control visible parts of the workflow. The public Cloud Run service and reproducible tests are available through the links in the project entry.

## Upload and verify

1. Watch the saved video once from beginning to end.
2. Confirm that the public URL, pause, resume, bounded result, approval message, and unverified-reference proof are readable.
3. Sign in to YouTube Studio, choose **Create**, then **Upload videos**, and select the saved file.
4. Use a clear title such as **BillWatch - All Things Agentic Hackathon Demo**.
5. Choose **Unlisted** unless you want the video publicly discoverable. Anyone with the link must be able to watch it.
6. Copy the final video URL and send it to Codex for the last preparation pass.
7. Test the link in a signed-out or private browser window before using it in Devpost.

YouTube's current upload instructions are here: https://support.google.com/youtube/answer/57407
