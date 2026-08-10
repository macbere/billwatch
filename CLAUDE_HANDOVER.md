# CLAUDE_HANDOVER.md — BillWatch Engineering Handover

**Prepared by:** Outgoing Claude Engineering Lead (session approaching context limit)
**For:** Incoming Claude Engineering Lead
**Date:** 2026-08-10
**Labeling key used throughout this document:**
- `[CONFIRMED — REPOSITORY]` — verified directly against actual repo files, git history, or a test run performed in this handover session
- `[EXTERNAL/PRIOR RESEARCH — VERIFY BEFORE FINAL SUBMISSION]` — established in prior conversation turns and delivered as standalone `.md` reports, but **not currently stored anywhere in this git repository**
- `[INFERENCE]` — a reasonable conclusion, not a directly stored fact
- `[UNKNOWN]` / `[NOT VERIFIED]` — explicitly unresolved

**Read this before anything else:** the entire pre-code discovery and architecture history (hackathon rules research, product-idea comparisons, the BillWatch selection reasoning, Phases 3.1–3.3A) exists **only** as `.md` files delivered in the prior chat session's outputs — **none of it is committed into this git repository**. This repo currently contains code and tests only. This is flagged again in Section 2/3/24 as a real gap, not glossed over.

---

## ⚠️ CRITICAL UNCOMMITTED-FILE CONFLICT — READ FIRST

`[CONFIRMED — REPOSITORY]` A file exists in the working tree that **is not committed, not tested, and not wired into anything**:
```
$ git status
On branch master
Untracked files:
  (use "git add <file>..." to include in what will be committed)
        billwatch/llm_provider.py

$ grep -n "llm_provider" billwatch/__init__.py
(no output -- not imported/exported anywhere)
```
This is a partial, abandoned-mid-session start on Build 4 (an `LLMProvider` abstract base class, a `MockLLMProvider` stub, and a stdlib-only `GeminiProvider`). **It has zero tests and has not been validated in any way.** Per this handover's own instruction ("if something conflicts, report it, do not silently choose"): **do not assume this file is correct, finished, or even wanted.** The incoming Claude should treat it as a draft to review, test from scratch, and either keep (with full adversarial tests added) or discard and rewrite — not as completed Build 4 work. Build 4 is authorized but **not completed**, and this file does not change that.

---

## SECTION 1 — Executive Project Summary

**What BillWatch is:** an agentic system that investigates a medical bill for billing errors by cross-referencing it against the patient's actual insurance policy/EOB and approved public reference data (CMS/CDC coding-relationship data), and — only when a discrepancy is genuinely evidence-supported — drafts a human-reviewed appeal.

**Problem it solves:** `[EXTERNAL/PRIOR RESEARCH]` medical billing errors are common and disputing them currently requires either the patient's own coding/policy literacy or hiring a paid human "medical billing advocate" — a real, pre-existing paid profession, which was treated as evidence of a validated market during product discovery.

**Who it's for:** `[EXTERNAL/PRIOR RESEARCH]` any patient with a confusing or possibly-incorrect medical bill — a broad, relatable consumer audience, deliberately chosen for hackathon judge comprehension.

**Why it matters / what's different:** the system does not simply ask an LLM "is this bill wrong?" It runs a structured, deterministic investigation pipeline in which an LLM may extract facts, propose hypotheses, and propose what to verify — but every consequential decision (is a source authoritative for this claim, is evidence sufficient, what is the final status, is an appeal eligible) is made by deterministic code, not the model. This evidence-first, deterministic-control philosophy **must be preserved**, not treated as a formality.

**What BillWatch deliberately does NOT do** `[CONFIRMED — REPOSITORY, enforced in code]`:
- Does not give medical or legal advice, or claim legal/medical certainty.
- Does not auto-send an appeal — appeal drafting is a **draft only**, gated so it is structurally unreachable outside one specific validated outcome.
- Does not treat the user's own stated belief/accusation as evidence.
- Does not treat CMS/NCCI (or any single source type) as universally authoritative.
- Does not reproduce AMA's copyrighted CPT descriptor text, under any circumstance.
- Does not guess an unknown case scope (Medicare vs. private) in either direction.

**Do not exaggerate capabilities:** as of this handover, BillWatch has **no LLM integration wired into any tested, working path**. Everything built and verified so far (Builds 1–3) is deterministic Python with zero model calls. Build 4 (LLM reasoning) is authorized but not completed — see the critical conflict note above.

---

## SECTION 2 — Hackathon Context

`[EXTERNAL/PRIOR RESEARCH — VERIFY BEFORE FINAL SUBMISSION]` — **none of the following is stored in this repository.** It was established via live web research in prior conversation turns and is recorded here from that research, not from anything checkable in the repo itself. **Re-verify all of it against the live Devpost page before final submission**, since hackathon rules/deadlines can change and this cannot be cross-checked from the repo alone.

- **Hackathon:** All Things Agentic Hackathon (`allthingsagentichackathon.devpost.com`), sponsored by Google LLC, administered by Devpost.
- **Track:** The Taskmaster (autonomous multi-step workflow agent, not a chatbot).
- **Mandatory tech stack (per prior research):** Gemini 3.5+ via Gemini API/Vertex AI; a Google agent framework (ADK/GenAI SDK/Antigravity SDK/Genkit); a Google Cloud infra service (e.g., Cloud Run, Firestore).
- **Judging weights (per prior research):** Innovation & Operational Utility 40%, Architectural Discipline & Tech Stack 30%, Demo & Production Readiness 30%, plus bonus points for a public content piece, a social post, and additional Google AI model integrations.
- **Submission deadline (per prior research):** Aug 31, 2026, 5:00 PM PT.
- **Demo requirement (per prior research):** ≤4-minute video; judges may not test the live app, so the video carries significant weight; must show proof of Google Cloud deployment.

**A. Confirmed project decisions:** BillWatch, Taskmaster track, deterministic-control architecture (all `[CONFIRMED — REPOSITORY]` via code).
**B. External hackathon research:** everything in the bullet list above.
**C. Assumptions:** none should be treated as assumptions — the above was researched, not assumed, but is unverifiable from the repo alone.
**D. Unresolved items:** whether the hackathon rules have changed since that research; whether the $150 GCP credit form was ever actually submitted `[UNKNOWN]`.

---

## SECTION 3 — Why BillWatch Was Selected

`[EXTERNAL/PRIOR RESEARCH]` — this reasoning lived across several discovery-phase reports, not in the repo. Summarized faithfully, not rewritten:

- **Dayrunner** (an email/calendar daily-ops agent) was the Phase 2 winner on a weighted rubric, but was later revisited and found to have a comparatively weak "why does this need agents" case — its workflow shape is largely fixed regardless of case content.
- **AgroScout** (crop-disease diagnosis via Gemini multimodal) briefly beat Dayrunner on a rubric re-score but was found, on fresh critique, to be closer to a smart image classifier than a genuinely agentic multi-step investigator.
- **ReliefMatch** (disaster-relief resource matching) scored well on genuine agentic necessity but was judged a well-worn, saturated hackathon genre with real demo-data sensitivity risk.
- **Genesis** (a dynamic, self-assembling multi-agent orchestration engine — "an engine looking for its ideal application") scored highest on Innovation/Technical Depth in a dedicated evaluation phase, but was rejected as the lead concept because its live-demo reliability risk was judged too high relative to the hackathon's Stage-One "must actually work" functionality gate.
- **Cybersecurity Incident Response** (as a possible Genesis application domain) scored highest in a domain-discovery exercise but was ultimately passed over in favor of a domain with a much lower risk of confusing non-specialist judges.
- **Investigative Journalism** (another Genesis domain candidate, and briefly a leading concept in its own right — "Genesis for Investigations") was found to have the best live-data credibility story of any concept evaluated (real, free, purpose-licensed public-records APIs), but was ultimately not selected — a later, purpose-first discovery reset explicitly did **not** carry forward any assumption that Genesis or its application domains were the answer.
- **BillWatch was selected via a dedicated "purpose-first" discovery reset** that deliberately did not assume any prior mechanism or domain, generated ~50 real-world candidate problems, eliminated whole trap categories (chatbots, RAG, private-data-dependent, medically unsafe, etc.), and selected BillWatch as the sole concept that passed all four mandatory tests applied to every finalist: **"Why does this need agents," "Remove AI and is it still compelling," "Would a judge remember this three days later," and "Could this become a company."** BillWatch's decisive advantage was the last test: medical billing advocacy is an already-existing, already-paid-for human profession, which was treated as unusually strong evidence for the concept's real-world viability at the hackathon stage.

**Do not rewrite this history** if asked to summarize why BillWatch was chosen — this is the actual chain of reasoning, not a simplified retrofit.

---

## SECTION 4 — Product Definition

`[CONFIRMED — REPOSITORY, encoded directly in code]`

- **Vision:** investigate a bill, tell the truth about what the evidence supports, draft an appeal only when genuinely warranted.
- **Target user:** a patient with a confusing/possibly-wrong medical bill.
- **Input:** an itemized bill, an EOB, and (ideally) the patient's plan/policy document.
- **Investigation workflow (as implemented through Build 3, deterministic parts only):** ingest → extract facts → establish case scope → generate hypotheses → retrieve reference evidence → verify against scope-conditional authority → detect conflicts → determine a final status → (only if supported) draft an appeal for human review.
- **Output:** one of four possible investigation outcomes (below), plus — only for one of them — a draft appeal.
- **Trust/safety model:** every claim traces to cited evidence with explicit provenance; nothing is ever presented as more certain than the evidence supports; the user's own belief is never itself evidence; appeals are drafts only, never auto-sent.
- **Limitations (current, honest):** no LLM reasoning is wired into any tested path yet; reference data is a small hand-compiled placeholder, not a real bulk import; no UI exists; nothing is deployed anywhere.

### The four investigation outcomes, and why all four matter
`[CONFIRMED — REPOSITORY]` — `billwatch/enums.py::FinalStatus`
1. **SUPPORTED_DISCREPANCY** — a real, evidence-corroborated billing error was found. The *only* status from which an appeal draft is reachable.
2. **NO_SUPPORTED_DISCREPANCY** — the bill was investigated and affirmatively found clean. A system that can only ever find problems isn't trustworthy; this status is tested as carefully as the positive case (see `tests/test_reference_data.py` and Build 3's report for the corresponding NCCI-scope test).
3. **INSUFFICIENT_EVIDENCE** — the honest "I don't know yet" outcome, with the specific missing evidence named. This is a first-class outcome, not a fallback error state.
4. **CONFLICTING_EVIDENCE** — two properly-in-scope sources disagree and the system does not silently pick a winner. Also first-class, never resolved by preference or confidence.

---

## SECTION 5 — Core Architectural Principle

> **"LLMs populate structured fields; deterministic code decides what those fields mean."**

`[CONFIRMED — REPOSITORY]` This is enforced, not aspirational, in every module built so far.

**LLM responsibilities (Build 4 scope, per authorization — not yet built/tested):**
- Evidence extraction (structured candidate fields from raw document text)
- Hypothesis generation (candidate explanations, explicitly not conclusions)
- Verification proposals (which reference/evidence source *types* to check — never whether that source is actually authoritative)

**Deterministic code responsibilities (all built and tested, Builds 1–3):**
- Case scope establishment (`billwatch/case_scope.py`)
- Source authority (`billwatch/authority.py`)
- Evidence admissibility / UserContext separation (`billwatch/evidence.py`, Gate 2)
- State transitions (`billwatch/state_machine.py`)
- Adjudication versioning (`billwatch/adjudication.py`)
- Reference data validation/lookup (`billwatch/reference_data.py`)
- Appeal eligibility (`billwatch/state_machine.py`, Gate 3)

Conflict handling and final adjudication logic *combining* these pieces into one coherent decision engine — beyond what Section 7 of Build 2's evidence-sufficiency description already specifies conceptually — has **not yet been implemented as running code**; Builds 1–3 built the pieces, not yet the full assembled adjudication flow. `[INFERENCE]` this is presumably Build 5's scope, but that has not been explicitly authorized yet as of this handover.

---

## SECTION 6 — Complete Architecture (current, as-built)

```
User
  ↓
Document Intake            [DETERMINISTIC -- exists conceptually; no file-intake
                             code built yet, Build 4 scope covers extraction INPUT
                             but not document upload/intake plumbing]
  ↓
Extraction                 [LLM -- Build 4, NOT YET BUILT]
                            [DETERMINISTIC validation -- NOT YET BUILT]
  ↓
Scope Classification       [DETERMINISTIC -- BUILT, billwatch/case_scope.py]
  ↓
Evidence Ledger            [DETERMINISTIC -- BUILT, billwatch/evidence.py]
  ↓
Hypothesis Generation      [LLM -- Build 4, NOT YET BUILT]
                            [DETERMINISTIC orphan-fact guard -- BUILT,
                             EvidenceLedger.add_hypothesis()]
  ↓
Source/Reference Retrieval [DETERMINISTIC -- BUILT, billwatch/reference_data.py]
  ↓
Verification               [LLM proposes targets -- Build 4, NOT YET BUILT]
                            [DETERMINISTIC authority check -- BUILT,
                             billwatch/authority.py::evaluate_source_authority]
  ↓
Conflict Detection          [DETERMINISTIC -- partially BUILT:
                             authority.py::flag_potential_conflict() detects
                             "both usable, neither wins" but does NOT resolve
                             content-level conflicts -- that's a later build]
  ↓
Evidence Sufficiency/       [DETERMINISTIC -- NOT YET BUILT as a single
Final Status                combined engine; the four FinalStatus values
                             exist (enums.py) and the state machine enforces
                             legal transitions, but nothing yet computes
                             which status a given ledger state deserves]
  ↓
Action Eligibility           [DETERMINISTIC -- BUILT, state_machine.py Gate 3]
  ↓
Appeal Draft                 [LLM -- NOT YET BUILT (explicitly out of Build 4
                             scope too; a later build)]
```

**Modules that exist today** `[CONFIRMED — REPOSITORY]`:
```
billwatch/
├── __init__.py            # public API surface (does NOT export llm_provider -- see conflict note)
├── enums.py                # SourceType, AuthorityLevel, CaseScopeValue, ScopeProvenance,
│                            # ValidationResult, FinalStatus, InvestigationState
├── user_context.py         # UserContext (deliberately separate from Evidence)
├── evidence.py             # Document, ExtractedFact, Source, Claim, Hypothesis,
│                            # SupportingEvidence, ContradictoryEvidence, Verification,
│                            # MissingEvidence, Conflict, EvidenceLedger
├── case_scope.py           # CaseScope + deterministic resolve_case_scope()
├── adjudication.py         # Adjudication (frozen, append-only history mixin)
├── state_machine.py        # InvestigationStateMachine, LEGAL_TRANSITIONS, Gate 3
├── investigation.py        # Investigation -- composition root
├── authority.py            # Build 2: ClaimType, AuthorityResult, evaluate_source_authority()
├── reference_data.py       # Build 3: HCPCS/ICD10/NCCI records, ReferenceStore, lookups
├── reference_bootstrap.py  # Build 3: small hand-compiled demo snapshot (NOT a real import)
└── llm_provider.py         # ⚠️ UNCOMMITTED, UNTESTED, NOT WIRED IN -- see conflict note
```
UI and deployment layers: `[NOT VERIFIED / do not exist]` — no UI code, no deployment scripts, no Dockerfile, no Cloud Run config anywhere in this repo as of this handover.

---

## SECTION 7 — Three Hard Safety Gates

`[CONFIRMED — REPOSITORY]` These are architectural invariants. **Do not weaken any of them, ever, for implementation convenience.**

### GATE 1 — Scope/Authority Protection
- **Original failure motivating it:** an early architecture draft said "CMS/NCCI is the sole controlling authority over conflicting sources" — the TEAM correctly rejected this, since CMS/NCCI is only authoritative within Medicare/Medicaid scope and does not automatically control private-insurer methodology.
- **Final solution:** authority is contextual per `(source_type, case_scope, claim_type)`, computed by `authority.py::evaluate_source_authority()`. CMS/NCCI on a private plan with no adoption evidence returns `CORROBORATING`, never `AUTHORITATIVE`.
- **Enforcement location:** `billwatch/authority.py`, `evaluate_source_authority()`.
- **Relevant tests:** `tests/test_authority.py::TestCmsNcciScopeRule` (the four required A/B/C/D scenarios); `tests/test_reference_data.py::test_14_ncci_lookup_success_does_not_auto_become_authoritative_for_private_plan` (proves a *successful reference-store lookup* still doesn't bypass this).
- **What must never be weakened:** no code path may ever grant `AUTHORITATIVE` to `CMS_NCCI` for a private-commercial case without an explicit, evidence-backed `ncci_adoption_evidence` `Source` of type `PLAN_POLICY`.

### GATE 2 — User-Bias Protection
- **Original failure motivating it:** risk that a user's strongly-worded accusation ("I know they overcharged me") could steer investigation toward confirming it (identified explicitly as a sycophancy risk in adversarial testing).
- **Final solution:** `UserContext` is a structurally separate type from `Source`/evidence, with no shared base class.
- **Enforcement location:** `billwatch/evidence.py::EvidenceLedger.add_source()` / `add_document()` (raises `TypeError` on a `UserContext`); re-verified independently at `billwatch/authority.py::evaluate_source_authority()`.
- **Relevant tests:** `tests/test_user_context_separation.py` (5 tests); `tests/test_authority.py::TestUserAssertionRejectedFromAuthorityPipeline` (tests the exact example phrases "I know they overcharged me," "The hospital definitely billed me twice," "I already proved this is wrong").
- **What must never be weakened:** no future component (including Build 4's extraction/hypothesis LLM components) may accept a `UserContext` object anywhere a `Source`/evidence input is expected.

### GATE 3 — Appeal-Anyway Protection
- **Original failure motivating it:** adversarial testing found that if appeal generation were only prompt-gated, a direct user instruction ("write my appeal anyway") could plausibly override a soft, prompt-level refusal.
- **Final solution:** appeal-draft generation is **code-gated**, not prompt-gated — `InvestigationStateMachine.request_draft_appeal()` raises unless `final_status == SUPPORTED_DISCREPANCY`, and the method signature itself accepts no instruction/message argument at all, so there is no natural-language surface to even attempt an override.
- **Enforcement location:** `billwatch/state_machine.py::InvestigationStateMachine.can_draft_appeal()` / `request_draft_appeal()`.
- **Forbidden transitions (hard-coded in `LEGAL_TRANSITIONS`):** `INSUFFICIENT_EVIDENCE → DRAFT_APPEAL`, `CONFLICTING_EVIDENCE → DRAFT_APPEAL`, `NO_SUPPORTED_DISCREPANCY → DRAFT_APPEAL` — all three explicitly tested in `tests/test_state_machine.py::TestForbiddenAppealTransitions`, including `test_no_user_instruction_can_bypass_the_gate`.
- **What must never be weakened:** Build 4/5's LLM components must never be given any code path that calls appeal generation directly — they may only ever produce hypotheses/proposals that feed into the deterministic pipeline upstream of this gate.

---

## SECTION 8 — Case Scope

`[CONFIRMED — REPOSITORY]` — `billwatch/case_scope.py`

- **Explicit structured user selection:** `establish_from_user_selection()` — matched against a fixed vocabulary (`medicare`, `medicaid`, `private`/`commercial`/`ppo`/`hmo`).
- **Deterministic validation of a source field:** `establish_from_validated_field()` — a regex match against a simplified Medicare-ID-shaped pattern, or the same fixed vocabulary. **Note:** this regex is explicitly documented in-code as a simplified placeholder, not a claim of full official MBI format compliance — flagged as a risk in both Build 1's and Build 2's own reports.
- **Provenance:** every `CaseScope` records `value`, `provenance` (`USER_SELECTED` / `VALIDATED_EOB_FIELD` / `VALIDATED_PLAN_DOCUMENT_FIELD` / `LLM_INFERENCE` / `NONE`), `source_identifier`, `timestamp`, `validation_result`.
- **Unknown scope:** `value = UNKNOWN`, `validation_result = FAIL`. Never silently defaults.
- **Conflicting scope:** if a user selection and a validated field both pass individually but *disagree*, the result is `UNKNOWN`/`FAIL`, not a preference for either — tested (`test_case_5_conflicting_scope_indicators_fail`).
- **LLM inference prohibition:** `reject_llm_inference_as_scope()` exists specifically to prove — by test, not just by absence — that an LLM's own guess, however confidently phrased, can never establish controlling scope (`test_case_4_llm_only_inference_never_establishes_scope`, plus `test_never_silently_defaults_to_medicare_or_private`).

**Why "probably Medicare" / "probably private insurance" is unacceptable:** a silent default in either direction would let the system apply Medicare-specific rules (or skip them) based on a guess, directly reopening exactly the overreach Gate 1 exists to prevent — the entire point of scope-conditional authority collapses if scope itself can be assumed rather than established.

---

## SECTION 9 — Source Authority

`[CONFIRMED — REPOSITORY]` — `billwatch/authority.py`

Authority is **contextual**, computed per `(source_type, case_scope, claim_type)` triple — there is no single global source ranking table anywhere in the codebase. The critical distinction the whole engine exists to enforce: **"found in the reference database" is not the same thing as "authoritative for this particular claim."** A successful `ReferenceStore` lookup (Build 3) only produces a `Source` object; that `Source` still has to pass through `evaluate_source_authority()` to get an actual authority result, and that call can still return `CORROBORATING`, `OUT_OF_SCOPE`, `INSUFFICIENT_SCOPE`, etc. — the lookup succeeding grants nothing by itself. This exact behavior is the subject of `tests/test_reference_data.py`'s test #14, considered the single most important regression guard in the reference-data layer.

**Private-plan NCCI behavior, exactly as implemented:**
```
Medicare/Medicaid scope + CMS_NCCI source        -> AUTHORITATIVE
Private scope + CMS_NCCI + no adoption evidence  -> CORROBORATING  (never AUTHORITATIVE)
Private scope + CMS_NCCI + explicit adoption evidence (a real PLAN_POLICY Source) -> AUTHORITATIVE
Unknown/unresolved scope                          -> INSUFFICIENT_SCOPE  (never guessed)
```

---

## SECTION 10 — Reference Data

`[CONFIRMED — REPOSITORY]` — `billwatch/reference_data.py`, `billwatch/reference_bootstrap.py`

- **HCPCS Level II, ICD-10-CM, CMS NCCI PTP relationships:** each modeled as a frozen dataclass (`HCPCSRecord`, `ICD10Record`, `NCCIPairRecord`) with mandatory provenance fields: `source`, `source_url`, `effective_date`, `version`, `retrieval_date`, `license_basis`, `scope`.
- **License basis:** validated against `APPROVED_LICENSE_BASES` (`public_domain_cms`, `public_domain_nchs`, `public_cms_ncci`) — anything else is rejected at load time, fail-closed, no warning-and-accept path exists anywhere.
- **Immutable snapshots:** `ReferenceStore.load_snapshot()` cannot overwrite an existing version; loading a new version never removes an old one (`tests/test_reference_data.py::TestSnapshotImmutabilityAndVersioning`).
- **Deterministic lookup:** `lookup_hcpcs()`, `lookup_icd10()`, `lookup_ncci_pair()` — unknown codes return `UNKNOWN` with `record=None`, never a guessed description.

**The CPT boundary, exactly as implemented:** `ReferenceStore.lookup_cpt_descriptor(code)` **always** returns `UNAVAILABLE`, for any input, and structurally never consults any snapshot at all — there is no code path anywhere in this repository capable of returning AMA CPT descriptor text, because none is ever stored. Bare CPT code numbers are permitted to appear only insofar as they come from a user's own uploaded document (handled outside this module). If licensed descriptor meaning is genuinely required for a claim and unavailable, the intended downstream behavior is `INSUFFICIENT_EVIDENCE` — though note: the actual "route to `INSUFFICIENT_EVIDENCE`" wiring for this specific case has not yet been built as part of a combined adjudication engine (see Section 6's gap note); today this is proven only at the reference-lookup level, not yet end-to-end.

---

## SECTION 11 — CMS/CDC Data Acquisition Limitation

`[CONFIRMED — REPOSITORY]` — verified directly, twice, in this project's actual build sessions (Build 3 and again in the current handover session):
```
$ curl -sI https://www.cms.gov
HTTP/2 403
x-deny-reason: host_not_allowed

$ curl -sI https://generativelanguage.googleapis.com
HTTP/2 403
x-deny-reason: host_not_allowed
```
This sandbox's network egress allowlist does not include `cms.gov`, `cdc.gov`, or `generativelanguage.googleapis.com`. **No bulk CMS/CDC file has ever been downloaded in this project.** The bootstrap reference dataset (`reference_bootstrap.py`) is explicitly, prominently documented in its own module docstring as **hand-compiled**, not a machine-extracted import — every record's `description_verified`/`relationship_verified` field is set to `False` for exactly this reason. The official source URLs cited in that file (CMS HCPCS quarterly-update page, CDC/NCHS ICD-10-CM files page, CMS NCCI PTP edits page) were independently verified via web search, which is a different and weaker claim than "downloaded and parsed."

**The documented real acquisition procedure** (for a future session with actual network access to `cms.gov`/`cdc.gov`) is written out in full in `BUILD3-REPORT.md` (delivered as a standalone file, **not currently copied into this repo** — see Section 24's risk list) — 7 explicit steps from download through validated load.

---

## SECTION 12 — Current Reference Data (exact contents)

`[CONFIRMED — REPOSITORY]` — `billwatch/reference_bootstrap.py`, verbatim:

| Dataset | Code(s) | Description/relationship | Verified? | Source | License basis |
|---|---|---|---|---|---|
| HCPCS | A0425 | "Ground mileage, per statute mile (ambulance transport)" | **False** | CMS HCPCS Level II Quarterly Update | `public_domain_cms` |
| HCPCS | E0143 | "Walker, folding, wheeled, adjustable or fixed height" | **False** | CMS HCPCS Level II Quarterly Update | `public_domain_cms` |
| ICD-10-CM | Z00.00 | "Encounter for general adult medical examination without abnormal findings" | **False** | CDC/NCHS ICD-10-CM Files | `public_domain_nchs` |
| ICD-10-CM | K57.30 | "Diverticulosis of large intestine without perforation or abscess without bleeding" | **False** | CDC/NCHS ICD-10-CM Files | `public_domain_nchs` |
| NCCI PTP | 45380/45378 | `column2_bundled_into_column1`, modifier indicator `0` | **False** | CMS Medicare NCCI PTP Edits (Practitioner Services) | `public_cms_ncci` |

No other reference records exist. This table is exhaustive as of this handover — do not assume additional records exist without checking `reference_bootstrap.py` directly.

---

## SECTION 13 — Build History (chronological)

| Build | Objective | Key implementation | Tests | Commit/tag | Status | Key risks |
|---|---|---|---|---|---|---|
| 1 | Evidence data model + state machine | `enums.py`, `user_context.py`, `evidence.py`, `case_scope.py`, `adjudication.py`, `state_machine.py`, `investigation.py` | 29 | `4f775a3` | PASSED | Simplified MBI regex; evidence-delta detection is ID-based |
| 2 | Deterministic authority engine | `authority.py`; strengthened `evidence.py` duplicate-id guard | +32 (61 total) | `8e6776e` (tag `build2-approved`) | PASSED | Jurisdiction-matching for `PUBLIC_REGULATORY` is a placeholder |
| Physical device verification | Confirm Build 2 on real Android/Termux | — | 61/61 re-run on-device | `8e6776e` (same commit) | **PASSED** — see Section 16 | Python 3.14 (device) vs 3.12.3 (build) — no discrepancy found |
| 3 | Reference data engine | `reference_data.py`, `reference_bootstrap.py` | +27 (88 total) | `7a94c1a` (tag `build3-approved`) | PASSED | Bootstrap data is illustrative only; real-file parsing untested |
| 4 | LLM reasoning (extraction/hypothesis/verification proposals) | — | — | **not committed** | **AUTHORIZED, NOT COMPLETED** | See critical conflict note at top of this document |

---

## SECTION 14 — Build 1 (detail)

`[CONFIRMED — REPOSITORY]`
- **Files/modules:** listed in Section 6.
- **Data model:** `Document`, `ExtractedFact`, `Source`, `Claim`, `Hypothesis`, `SupportingEvidence`, `ContradictoryEvidence`, `Verification`, `MissingEvidence`, `Conflict` — all frozen dataclasses, append-only via `EvidenceLedger`.
- **State machine:** allow-list `LEGAL_TRANSITIONS` covering `INGESTED → ... → ADJUDICATED`, with the only exit from `ADJUDICATED` being back to `EVIDENCE_RETRIEVED` (restart path).
- **UserContext/Evidence separation:** enforced at `EvidenceLedger.add_source()`/`add_document()`.
- **CaseScope:** as detailed in Section 8.
- **Adjudication versioning:** append-only, frozen, `supersedes_adjudication_id` + mandatory `reason_for_reassessment` on any restart; restart rejected if the evidence snapshot hasn't actually changed.
- **Tests:** 29.
- **Original test count:** **29/29 tests passed**, per the Build 1 report and re-confirmed by a fresh run in this handover session against the exact `4f775a3` commit content (as part of the full 88-test current suite, which includes these 29 unmodified).
- **Architectural deviations:** one organizational-only deviation (adjudication logic split into a mixin composed into `Investigation`) — no behavioral change.

---

## SECTION 15 — Build 2 (detail)

`[CONFIRMED — REPOSITORY]`
- **Deterministic authority engine:** `authority.py::evaluate_source_authority()`.
- **Scope-conditional authority:** Section 9, above.
- **CMS/NCCI behavior:** the A/B/C/D scenario table, Section 9.
- **Provenance:** every `AuthorityDecision` records `source_id`, `source_type`, `case_scope_value`, `case_scope_validation`, `source_scope`, `claim_type`, `rule_applied` (a specific named rule string), `result`, `rationale`.
- **Evidence immutability:** strengthened with a duplicate-id rejection guard added to every `EvidenceLedger.add_*` method.
- **Tests:** 32 new.
- **Test count:** **61/61 tests passed** (29 Build 1 + 32 Build 2), confirmed in the Build 2 report and re-confirmed by physical device execution (Section 16).
- **Approved commit/tag:** `8e6776e`, tag `build2-approved`.

---

## SECTION 16 — Physical Device Verification

`[CONFIRMED — REPOSITORY / prior verification report]`
- **Device:** Project Owner's actual Android phone, Termux.
- **Python version on device:** **3.14** (vs. 3.12.3 in the build sandbox — a real, disclosed difference; no test behavior discrepancy was found).
- **Exact commit/tag verified:** `8e6776e` / `build2-approved`.
- **Result:** `Ran 61 tests ... OK` — **61/61 passed**.
- **Git tree:** confirmed clean immediately post-extraction, before the test run.
- **Regression status:** all 29 Build 1 tests + all 32 Build 2 tests passed together, unmodified, on-device.

**Not yet done:** Build 3 (`7a94c1a`/`build3-approved`) has **not** been independently verified on the physical device — only Build 2 was. Do not conflate the two. This gap is also flagged in `BUILD3-REPORT.md` Section 16 (external file, not in this repo) and should be closed before final submission.

---

## SECTION 17 — Build 3 (detail)

`[CONFIRMED — REPOSITORY]`
- **Reference store:** `ReferenceStore` — versioned, immutable, fail-closed loader (Section 10).
- **HCPCS / ICD-10-CM / NCCI:** Section 10/12.
- **Provenance/licensing:** Section 10.
- **CPT restrictions:** Section 10, "The CPT boundary" paragraph.
- **Bootstrap data:** Section 12 (exact table).
- **CMS connectivity limitation:** Section 11.
- **Deterministic scope integration:** `ReferenceStore.to_source()` never assigns authority; proven by `test_14_ncci_lookup_success_does_not_auto_become_authoritative_for_private_plan`.
- **Tests:** 27 new.
- **Test count:** **88/88 tests passed** (61 prior + 27 Build 3), confirmed in the Build 3 report and re-confirmed by a fresh run in this handover session.
- **Commit/tag:** `7a94c1a`, tag `build3-approved`.

---

## SECTION 18 — Current Test Inventory

`[CONFIRMED — REPOSITORY]` — counted directly (`grep -c "    def test_"` per file) in this handover session:

| Test file | Purpose | # tests | Security/safety significance | Build introduced |
|---|---|---|---|---|
| `test_user_context_separation.py` | Gate 2 — UserContext cannot be Evidence | 5 | Critical (Gate 2) | 1 |
| `test_case_scope.py` | Deterministic scope provenance, all 6 required cases | 9 | Critical (Gate 1 precondition) | 1 |
| `test_adjudication.py` | Append-only versioning + immutability | 5 | High (audit integrity) | 1 |
| `test_state_machine.py` | Legal transitions + Gate 3 (all 3 forbidden appeal paths) | 10 | Critical (Gate 3) | 1 |
| `test_authority.py` | Scope-conditional authority, CMS/NCCI A/B/C/D, conflict prep, adversarial input guards | 29 | Critical (Gate 1) | 2 |
| `test_evidence_immutability.py` | Strengthened duplicate-id guard | 3 | Medium | 2 |
| `test_reference_data.py` | HCPCS/ICD/NCCI lookup, fail-closed validation, CPT boundary, authority-bypass regression | 27 | Critical (CPT boundary + Gate 1 regression) | 3 |
| **Total** | | **88** | | |

**Regression counts:** Build 2 re-ran and passed all 29 Build 1 tests unmodified; Build 3 re-ran and passed all 61 prior tests unmodified. Zero regressions across all three builds, confirmed by this handover's own fresh test run.

---

## SECTION 19 — Current Git State

`[CONFIRMED — REPOSITORY, this session]`
```
Branch: master
HEAD: 7a94c1aa87be04bec202c996d603a596b3a24f99  (short: 7a94c1a)
Tags:
  build2-approved -> 8e6776e
  build3-approved -> 7a94c1a  (== current HEAD)

Status: clean on all TRACKED files (git diff --stat shows nothing)
Untracked: billwatch/llm_provider.py  (see critical conflict note)

Recent commits:
  7a94c1a (HEAD -> master, tag: build3-approved) Build 3: Approved reference data + deterministic lookup
  8e6776e (tag: build2-approved) Build 2: Deterministic Source/Scope authority engine
  4f775a3 Build 1: Evidence data model + state machine
```

---

## SECTION 20 — Build 4 Authorization

**BUILD 4 IS AUTHORIZED. BUILD 4 HAS NOT BEEN COMPLETED.** Do not assume otherwise — see the critical conflict note at the top of this document regarding the one stray, untested `llm_provider.py` file.

**Authorized Build 4 scope** `[EXTERNAL/PRIOR RESEARCH — the authorization document itself, not in this repo]`:
1. Evidence extraction (LLM-backed, strictly structured output)
2. Hypothesis generation (candidates, never conclusions)
3. Verification planning/reasoning (proposes source *types* to check, never decides authority)
4. A controlled Gemini/provider boundary (abstraction so the reasoning layer is testable without live Gemini)
5. Structured model outputs only — no free-form prose treated as authoritative
6. Deterministic validation of all model output
7. Model failure handling (malformed JSON, timeouts, hallucination, etc. → safe failure, never a guess)
8. A substantial adversarial test suite (see Section 22)

**Build 4 must NOT implement:** final adjudication, conflict resolution, appeal generation, UI, or deployment.

---

## SECTION 21 — Gemini Boundary

`[EXTERNAL/PRIOR RESEARCH — the authorization document]`, consistent with `[CONFIRMED — REPOSITORY]` architecture already in place:

**Allowed:** evidence extraction, hypothesis generation, verification proposals.
**Not allowed, under any framing:** final status, CaseScope, source authority, evidence admissibility, conflict resolution, appeal eligibility, state-transition authority.

**"Prompt instructions are not security boundaries."** Every one of the "not allowed" items above already has a deterministic enforcement point built and tested in this repo (Sections 7–9). Build 4's job is to add LLM components **upstream** of those gates, never to touch the gates themselves. If a Build 4 implementation idea would require loosening any gate to work, that is a signal the idea is wrong, not that the gate should change.

---

## SECTION 22 — Build 4 Test Requirements

`[EXTERNAL/PRIOR RESEARCH — the authorization document]` — the full required adversarial list, to be implemented against whatever Build 4 code is (re)written:

hallucinated evidence · invented codes · invented amounts · invented dates · missing evidence · malformed JSON · unknown evidence IDs · unsupported sources · UserContext contamination · confident-but-wrong output · clean bill (zero hypotheses) · multiple competing hypotheses · zero hypotheses · Gemini unavailable · Gemini timeout · Gemini malformed response · model proposes an out-of-scope source · model attempts to determine final status · model attempts to declare appeal eligibility.

For the last two: the system must either reject the output outright or ignore the unauthorized fields — either is acceptable per the authorization, but whichever is chosen must be tested explicitly, not assumed.

---

## SECTION 23 — What Must Never Change (architectural invariants)

`[CONFIRMED — REPOSITORY, all currently enforced in code]`
1. UserContext is not Evidence.
2. Unknown scope cannot be guessed.
3. CMS/NCCI is not globally authoritative.
4. LLM confidence cannot override deterministic rules.
5. Hypothesis ≠ conclusion.
6. Reference lookup ≠ authoritative adjudication.
7. Existing adjudications are append-only.
8. Existing evidence is not silently mutated (frozen dataclasses + duplicate-id rejection).
9. Insufficient evidence is a valid first-class outcome.
10. Conflicting evidence is a valid first-class outcome.
11. Appeal generation is deterministically (code-, not prompt-) gated.
12. CPT copyrighted descriptor text is not reproduced, anywhere, ever.
13. No prompt-only safety boundary may replace a required code-level gate.
14. No later build may weaken an earlier safety invariant merely to make implementation easier.

---

## SECTION 24 — Known Risks

**CRITICAL**
- The one uncommitted, untested `llm_provider.py` file could be mistaken for validated Build 4 progress if not read carefully — flagged prominently at the top of this document specifically to prevent that.
- Build 3 has not been physically device-verified (only Build 2 has) — a real, open gap before final submission.

**HIGH**
- Gemini hallucination risk in Build 4 extraction/hypothesis/verification components is the entire reason Build 4's adversarial test list (Section 22) exists — must not be under-tested.
- Gemini API availability: `[CONFIRMED]` no key present and no network path to `generativelanguage.googleapis.com` in this sandbox — Build 4's deterministic tests must not depend on live Gemini access, per the authorization's own explicit instruction.
- **This repository does not contain the prior discovery/architecture `.md` reports** (Phases 1 through 3.3A) — they exist only as previously-delivered chat output files. If those files are lost or inaccessible to a future session, a meaningful amount of documented reasoning (Section 3's history, the hackathon research in Section 2) would have no durable home. **Recommend copying `BUILD1-REPORT.md`, `BUILD2-REPORT.md`, `BUILD3-REPORT.md`, and the Phase 1–3.3A reports into the repo itself** (e.g., a `docs/` directory) in a future session.

**MEDIUM**
- Reference data completeness: only 5 illustrative records exist total; a real submission needs either a genuine bulk import (requires network access this sandbox doesn't have) or a carefully hand-curated, larger, fully-cited demo-scoped set.
- The simplified Medicare-ID regex in `case_scope.py` needs replacement with real CMS MBI format rules before any real data touches it.
- `PUBLIC_REGULATORY` jurisdiction-matching in `authority.py` is a documented placeholder (`ADMISSIBLE`, never `AUTHORITATIVE`) pending real jurisdiction reference data.

**LOW**
- Termux compatibility: strong so far (zero non-stdlib dependencies across all of Builds 1–3); Build 4's `GeminiProvider` was drafted stdlib-only (`urllib.request`) specifically to preserve this, but that draft is itself unverified (see Critical Uncommitted-File note).
- Demo reliability / production readiness / privacy-security / hackathon compliance: not yet assessable — no UI, no deployment, no live-data handling exists yet to evaluate.

---

## SECTION 25 — DO NOT DO LIST

- DO NOT redesign BillWatch or reopen product discovery.
- DO NOT switch hackathons or import requirements from any other hackathon/project.
- DO NOT introduce unnecessary multi-agent architecture (Build 1's own finding: a fixed pipeline with one conditional branch outperforms dynamic orchestration for this specific product).
- DO NOT weaken any of the three hard gates (Section 7) or the 14 invariants (Section 23).
- DO NOT treat user claims/assertions as evidence, anywhere, including inside Build 4's extraction component.
- DO NOT let Gemini (or any LLM) adjudicate, set scope, or authorize an appeal.
- DO NOT add AMA CPT descriptor text anywhere, under any framing.
- DO NOT silently resolve source conflicts — always surface them.
- DO NOT fabricate reference data or claim a source was accessed when it was not (see Section 11's exact standard).
- DO NOT skip tests, and do not treat an untested file as "done" (see the Critical Uncommitted-File note — this almost happened once already in this project).
- DO NOT skip ChatGPT's architecture approval at any authorized milestone.
- DO NOT begin Build 5 before Build 4 is reviewed and authorized.

---

## SECTION 26 — Next Action

**The next action is BUILD 4 IMPLEMENTATION.** Before writing any code, the incoming Claude must:
1. Read this document in full.
2. Independently re-run `git status`, `git log --oneline --decorate`, and `python3 -m unittest discover -s tests -v` — do not trust this document's numbers without re-confirming them, exactly as this document was itself produced by inspecting the repo rather than trusting memory.
3. Make an explicit decision about `billwatch/llm_provider.py`: keep-and-test-from-scratch, or discard-and-rewrite. Either is fine; silently ignoring it is not.
4. Confirm understanding of the three hard gates and 14 invariants before writing any Build 4 code that touches extraction, hypothesis, or verification-proposal logic.
5. Wait for ChatGPT's explicit Build 4 implementation direction if anything in this handover is ambiguous.

---

## SECTION 27 — Handover Checklist

- [x] Hackathon identity confirmed (Section 2, flagged as external research)
- [x] BillWatch identity confirmed (Section 1)
- [x] Team roles documented (this document's header context + original authorization text)
- [x] Product definition documented (Section 4)
- [x] Architecture documented (Section 6)
- [x] Safety gates documented (Section 7)
- [x] Build 1 documented (Section 14)
- [x] Build 2 documented (Section 15)
- [x] Physical verification documented (Section 16)
- [x] Build 3 documented (Section 17)
- [x] Reference data documented (Sections 10, 12)
- [x] Licensing documented (Sections 10, 11)
- [x] Git state documented (Section 19)
- [x] Tests documented (Section 18)
- [x] Build 4 authorization documented (Section 20)
- [x] Known risks documented (Section 24)
- [x] Invariants documented (Section 23)
- [x] Next action documented (Section 26)
