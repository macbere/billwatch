# BillWatch Architecture

BillWatch has two related execution paths:

- The public path in app.py accepts arbitrary bill text and returns a bounded evidence report.
- The fuller domain path in billwatch/pipeline.py exercises the staged investigation state machine and remains covered by the domain tests.

## Submitted product boundary

The canonical submitted architecture diagram is [`output/pdf/billwatch-hackathon-architecture.pdf`](output/pdf/billwatch-hackathon-architecture.pdf). The same diagram is intended for GitHub review, Devpost upload, and the final demo video.

The **submitted BillWatch product** is the public Taskmaster workflow exposed through `app.py`.

The repository also contains the fuller domain pipeline in `billwatch/pipeline.py`. That pipeline is retained as supporting engineering architecture and regression coverage, but it is not presented as the currently exposed public web workflow.

For the submitted product, BillWatch autonomously performs request validation, evidence extraction, exact-evidence validation, candidate identification, unique-pair expansion, bounded reference checks, applicability gates, missing-context identification, and bounded result generation.

Human confirmation is a deliberate evidence or consequential-action boundary. It is not the mechanism performing the investigation.

The ordinary-input path uses Gemini 3.5 Flash through the Google GenAI SDK when `GEMINI_API_KEY` is configured. Gemini output remains untrusted. The separately selected synthetic demonstration is deterministic and isolated from the ordinary-input path.

## Public request path

    Browser
       |
       v
    POST /investigate
       |
       +--> request-size and per-IP rate limits
       |
       +--> JSON and context validation
       |
       +--> Document(raw bill text)
       |
       +--> LLM extraction when GEMINI_API_KEY is present
       |       or input-driven offline extraction when it is absent
       |
       +--> strict source-span and value containment validation
       |
       +--> deterministic code-candidate scan
       |
       +--> every unique code pair
       |       |
       |       +--> ReferenceStore lookup
       |       +--> effective-date check
       |       +--> reference verification and payer-scope checks
       |       +--> modifier-indicator check
       |
       +--> JSON result for human review

The public path never turns a matching code pair into a definitive billing error. It can return POTENTIAL_DISCREPANCY only when the loaded relationship is independently verified, the payer scope is Medicare, the required claim context is present, and the reference rules permit that conclusion. The checked-in illustrative relationship is unverified, so it returns REFERENCE_UNVERIFIED.

## Full internal pipeline

    Document(s)
         |
         v
    Evidence extraction
      LLM proposes facts
      llm_schemas.py validates source spans and values
      EvidenceLedger records accepted facts
         |
         v
    Case scope
      deterministic Medicare/Medicaid/private resolution
         |
         v
    Hypothesis proposal
      LLM proposes a candidate explanation
      schema validation rejects domain-decision smuggling
         |
         v
    Verification
      LLM proposes source categories
      deterministic reference lookup
      authority.py evaluates source plus scope plus claim type
      conflicts are flagged but never silently resolved
         |
         v
    Adjudication
      pure deterministic Python computes final status
         |
         +--> appeal drafting only through the existing state-machine gate

## Trust boundaries

1. LLM output is untrusted input. It cannot set scope, authority, final status, or appeal eligibility.
2. A user assertion is context, not evidence.
3. A reference lookup is not automatically an authority decision.
4. Medicare NCCI data is not Medicaid data and is not private-plan policy.
5. Repeating the same semantic source does not create a conflict solely because generated IDs differ.
6. Missing, stale, or unverified reference data produces an honest insufficient-context result.

## Current limitations

- The public UI accepts text-oriented TXT, CSV, and JSON files; OCR/PDF ingestion is not implemented.
- The checked-in CMS/NCCI fixture is illustrative and unverified.
- Medicaid-specific NCCI data, private-plan policy ingestion, and live reference refresh are not yet implemented.
- Public live Gemini use still needs production authentication, stronger abuse controls, and cost monitoring.
- Browser behavior requires manual verification on desktop and mobile.
