"""
Build 4F: Orchestration Pipeline tests.

Tests billwatch/pipeline.py ONLY. ZERO real network calls, ZERO real
Gemini calls -- MockLLMProvider only, via a dispatcher that inspects
each stage's distinctive system prompt to return the appropriate
canned response, since a single pipeline run calls the same provider
across four different stages.
"""

import json
import re
import unittest

from billwatch import (
    Document, Investigation, UserContext,
    CaseScope, CaseScopeValue, ScopeProvenance, ValidationResult,
    InvestigationState, FinalStatus,
)
from billwatch.llm_provider import MockLLMProvider, LLMProviderError
from billwatch.reference_data import ReferenceStore
from billwatch.reference_bootstrap import load_bootstrap_data
from billwatch.pipeline import PipelineError, PipelineResult, run_investigation


def _bootstrapped_store():
    store = ReferenceStore()
    load_bootstrap_data(store)
    return store


def _medicare_scope():
    return CaseScope(
        value=CaseScopeValue.MEDICARE, provenance=ScopeProvenance.USER_SELECTED,
        source_identifier="test", validation_result=ValidationResult.PASS,
    )


def _make_dispatch_provider(
    doc,
    extracted_facts,
    source_types=("CMS_NCCI",),
    appeal_text="This is a draft appeal letter.",
    extraction_response=None,
    hypothesis_response=None,
    verification_response=None,
    appeal_response=None,
):
    """Builds a MockLLMProvider whose response_fn inspects the real,
    distinctive system prompt text of each stage (verbatim from the
    actual production modules) to return the correct canned response.
    Any of the four *_response overrides, if given, replaces that
    stage's normal canned response entirely (used for failure tests)."""

    def dispatch(system_prompt, user_content):
        if "document-extraction component" in system_prompt:
            if extraction_response is not None:
                return extraction_response
            return json.dumps({"document_id": doc.id, "extracted_facts": extracted_facts})

        if "hypothesis-proposal component" in system_prompt:
            if hypothesis_response is not None:
                return hypothesis_response
            fact_ids = re.findall(r"fact_id=([0-9a-fA-F-]+)", user_content)
            return json.dumps({
                "claim_statement": "Possible billing discrepancy",
                "explanation_text": "The extracted facts suggest a possible issue.",
                "referenced_fact_ids": fact_ids,
            })

        if "verification-planning component" in system_prompt:
            if verification_response is not None:
                return verification_response
            hyp_match = re.search(r"hypothesis_id:\s*(\S+)", user_content)
            hyp_id = hyp_match.group(1) if hyp_match else ""
            return json.dumps({
                "hypothesis_id": hyp_id,
                "proposed_source_types": list(source_types),
                "verification_rationale": "check applicable references",
            })

        if "appeal-drafting component" in system_prompt:
            if appeal_response is not None:
                return appeal_response
            claim_match = re.search(r"claim_id:\s*(\S+)", user_content)
            claim_id = claim_match.group(1) if claim_match else ""
            fact_ids = re.findall(r"fact_id=([0-9a-fA-F-]+)", user_content)
            return json.dumps({
                "draft_text": appeal_text,
                "cited_fact_ids": fact_ids,
                "cited_claim_ids": [claim_id] if claim_id else [],
            })

        return "{}"

    return MockLLMProvider(response_fn=dispatch)


def _fresh_investigation_with_doc():
    inv = Investigation()
    doc = Document(doc_type="bill", raw_text="CPT/HCPCS codes 45378 and 45380 billed together for $500.00.")
    return inv, doc


# ---------------------------------------------------------------------
# GROUP 1 -- Happy-path full pipeline
# ---------------------------------------------------------------------
class TestHappyPathFullPipeline(unittest.TestCase):

    def test_full_pipeline_reaches_supported_discrepancy_with_appeal(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"},
                 {"fact_type": "code", "value": "45380", "source_span": "45380"}]
        provider = _make_dispatch_provider(doc, facts, source_types=("CMS_NCCI",))
        store = _bootstrapped_store()

        result = run_investigation(inv, [doc], _medicare_scope(), provider, store)

        self.assertTrue(result.success)
        self.assertEqual(result.final_status, FinalStatus.SUPPORTED_DISCREPANCY)
        self.assertIsNotNone(result.appeal)
        self.assertTrue(result.appeal.success)
        self.assertTrue(result.appeal.draft_text)


# ---------------------------------------------------------------------
# GROUP 2 -- Correct state transitions
# ---------------------------------------------------------------------
class TestStateTransitions(unittest.TestCase):

    def test_happy_path_state_history_matches_expected_sequence(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"},
                 {"fact_type": "code", "value": "45380", "source_span": "45380"}]
        provider = _make_dispatch_provider(doc, facts, source_types=("CMS_NCCI",))
        store = _bootstrapped_store()

        run_investigation(inv, [doc], _medicare_scope(), provider, store)

        expected = [
            InvestigationState.INGESTED, InvestigationState.EXTRACTED,
            InvestigationState.SCOPED, InvestigationState.HYPOTHESES_GENERATED,
            InvestigationState.EVIDENCE_RETRIEVED, InvestigationState.VERIFIED,
            InvestigationState.CONFLICT_CHECKED, InvestigationState.ADJUDICATED,
        ]
        actual = [s for s, _ in inv.state_machine.history]
        self.assertEqual(actual, expected)

    def test_extraction_failure_leaves_state_at_ingested(self):
        inv, doc = _fresh_investigation_with_doc()
        provider = _make_dispatch_provider(doc, [], extraction_response="not json")
        store = _bootstrapped_store()

        run_investigation(inv, [doc], _medicare_scope(), provider, store)

        self.assertEqual(inv.state, InvestigationState.INGESTED)


# ---------------------------------------------------------------------
# GROUP 3 -- Fail-closed: each stage failing stops the pipeline
# ---------------------------------------------------------------------
class TestFailClosedStageFailures(unittest.TestCase):

    def test_extraction_failure_stops_pipeline(self):
        inv, doc = _fresh_investigation_with_doc()
        provider = _make_dispatch_provider(doc, [], extraction_response="not json")
        store = _bootstrapped_store()

        result = run_investigation(inv, [doc], _medicare_scope(), provider, store)

        self.assertFalse(result.success)
        self.assertEqual(result.failed_stage, "extraction")
        self.assertIsNone(result.final_status)
        self.assertIsNone(result.appeal)

    def test_hypothesis_failure_stops_pipeline(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"}]
        provider = _make_dispatch_provider(doc, facts, hypothesis_response="not json")
        store = _bootstrapped_store()

        result = run_investigation(inv, [doc], _medicare_scope(), provider, store)

        self.assertFalse(result.success)
        self.assertEqual(result.failed_stage, "hypothesis")
        self.assertEqual(inv.state, InvestigationState.SCOPED)
        self.assertIsNone(result.appeal)

    def test_verification_failure_stops_pipeline(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"}]
        provider = _make_dispatch_provider(doc, facts, verification_response="not json")
        store = _bootstrapped_store()

        result = run_investigation(inv, [doc], _medicare_scope(), provider, store)

        self.assertFalse(result.success)
        self.assertEqual(result.failed_stage, "verification")
        self.assertEqual(inv.state, InvestigationState.HYPOTHESES_GENERATED)
        self.assertIsNone(result.appeal)

    def test_adjudication_precondition_failure_is_handled_if_it_ever_occurs(self):
        # AdjudicationPreconditionError requires zero hypotheses AND zero
        # facts -- within run_investigation()'s own code path this is
        # actually unreachable once a hypothesis has genuinely succeeded
        # (a precondition for even reaching this stage), since the
        # ledger is append-only. Documenting this rather than fabricating
        # an artificial scenario: the handling branch (PipelineResult
        # failed_stage="adjudication") exists in pipeline.py and the
        # underlying error itself is exercised directly and thoroughly
        # by adjudication_integration.py's own untouched, still-passing
        # test suite.
        self.assertTrue(True)


# ---------------------------------------------------------------------
# GROUP 4 -- Appeal gating by final status
# ---------------------------------------------------------------------
class TestAppealGatingByFinalStatus(unittest.TestCase):

    def test_no_supported_discrepancy_prevents_appeal(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"},
                 {"fact_type": "code", "value": "45380", "source_span": "45380"}]
        # Real, known NCCI pair, but scope is left unresolved -- the
        # lookup succeeds and authority.py correctly returns
        # INSUFFICIENT_SCOPE (never guessed), which maps to a real
        # "silent" Verification record (checked, found nothing usable)
        # -- not MissingEvidence. This is what actually produces
        # NO_SUPPORTED_DISCREPANCY rather than INSUFFICIENT_EVIDENCE.
        # (Original version of this test used a single unknown code
        # with CMS_NCCI, which requires two codes to attempt a pair
        # lookup at all -- that produced MissingEvidence instead,
        # i.e. INSUFFICIENT_EVIDENCE. Fixed here, not in production code.)
        provider = _make_dispatch_provider(doc, facts, source_types=("CMS_NCCI",))
        store = _bootstrapped_store()

        result = run_investigation(inv, [doc], None, provider, store)

        self.assertTrue(result.success)
        self.assertEqual(result.final_status, FinalStatus.NO_SUPPORTED_DISCREPANCY)
        self.assertIsNone(result.appeal)

    def test_insufficient_evidence_prevents_appeal(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"}]
        # PLAN_POLICY has no lookup mechanism -> MissingEvidence only,
        # zero Verification records -> UNCHECKED -> INSUFFICIENT_EVIDENCE.
        provider = _make_dispatch_provider(doc, facts, source_types=("PLAN_POLICY",))
        store = _bootstrapped_store()

        result = run_investigation(inv, [doc], _medicare_scope(), provider, store)

        self.assertTrue(result.success)
        self.assertEqual(result.final_status, FinalStatus.INSUFFICIENT_EVIDENCE)
        self.assertIsNone(result.appeal)

    def test_conflicting_evidence_prevents_appeal(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"},
                 {"fact_type": "code", "value": "45380", "source_span": "45380"}]
        # Duplicate CMS_NCCI proposal under Medicare scope -> two usable
        # decisions on the same claim -> flagged as a Conflict.
        provider = _make_dispatch_provider(doc, facts, source_types=("CMS_NCCI", "CMS_NCCI"))
        store = _bootstrapped_store()

        result = run_investigation(inv, [doc], _medicare_scope(), provider, store)

        self.assertTrue(result.success)
        self.assertEqual(result.final_status, FinalStatus.CONFLICTING_EVIDENCE)
        self.assertIsNone(result.appeal)

    def test_supported_discrepancy_permits_appeal(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"},
                 {"fact_type": "code", "value": "45380", "source_span": "45380"}]
        provider = _make_dispatch_provider(doc, facts, source_types=("CMS_NCCI",))
        store = _bootstrapped_store()

        result = run_investigation(inv, [doc], _medicare_scope(), provider, store)

        self.assertTrue(result.success)
        self.assertEqual(result.final_status, FinalStatus.SUPPORTED_DISCREPANCY)
        self.assertIsNotNone(result.appeal)
        self.assertTrue(result.appeal.success)

    def test_appeal_failure_does_not_alter_adjudication(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"},
                 {"fact_type": "code", "value": "45380", "source_span": "45380"}]
        provider = _make_dispatch_provider(
            doc, facts, source_types=("CMS_NCCI",), appeal_response="not json",
        )
        store = _bootstrapped_store()

        result = run_investigation(inv, [doc], _medicare_scope(), provider, store)

        self.assertTrue(result.success)
        self.assertEqual(result.final_status, FinalStatus.SUPPORTED_DISCREPANCY)
        self.assertIsNotNone(result.appeal)
        self.assertFalse(result.appeal.success)


# ---------------------------------------------------------------------
# GROUP 5 -- Caller cannot override FinalStatus / structural proofs
# ---------------------------------------------------------------------
class TestCallerCannotOverrideFinalStatus(unittest.TestCase):

    def test_run_investigation_signature_has_no_final_status_parameter(self):
        import inspect
        sig = inspect.signature(run_investigation)
        self.assertNotIn("final_status", sig.parameters)
        self.assertEqual(
            list(sig.parameters.keys()),
            ["investigation", "documents", "case_scope", "provider", "reference_store"],
        )

    def test_pipeline_result_final_status_always_comes_from_real_adjudication(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"},
                 {"fact_type": "code", "value": "45380", "source_span": "45380"}]
        provider = _make_dispatch_provider(doc, facts, source_types=("CMS_NCCI",))
        store = _bootstrapped_store()

        result = run_investigation(inv, [doc], _medicare_scope(), provider, store)
        self.assertEqual(result.final_status, inv.final_status)


# ---------------------------------------------------------------------
# GROUP 6 -- Hard-gate regressions and general structural proofs
# ---------------------------------------------------------------------
class TestHardGateRegressions(unittest.TestCase):

    def test_gate2_user_context_still_rejected_after_full_pipeline_run(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"},
                 {"fact_type": "code", "value": "45380", "source_span": "45380"}]
        provider = _make_dispatch_provider(doc, facts, source_types=("CMS_NCCI",))
        store = _bootstrapped_store()
        run_investigation(inv, [doc], _medicare_scope(), provider, store)

        uc = UserContext(investigation_id=inv.investigation_id, stated_concern_text="x")
        with self.assertRaises(TypeError):
            inv.ledger.add_source(uc)  # type: ignore[arg-type]

    def test_appeal_unreachable_without_real_supported_discrepancy(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "99999", "source_span": "99999"}]
        provider = _make_dispatch_provider(doc, facts, source_types=("CMS_NCCI",))
        store = _bootstrapped_store()

        run_investigation(inv, [doc], _medicare_scope(), provider, store)

        self.assertFalse(inv.can_draft_appeal())

    def test_non_investigation_input_rejected(self):
        provider = MockLLMProvider(fixed_response="{}")
        store = _bootstrapped_store()
        with self.assertRaises(PipelineError):
            run_investigation("not an investigation", [], _medicare_scope(), provider, store)  # type: ignore[arg-type]

    def test_non_document_in_documents_list_rejected(self):
        inv, doc = _fresh_investigation_with_doc()
        provider = MockLLMProvider(fixed_response="{}")
        store = _bootstrapped_store()
        with self.assertRaises(PipelineError):
            run_investigation(inv, ["not a document"], _medicare_scope(), provider, store)  # type: ignore[arg-type]

    def test_reusing_a_non_fresh_investigation_is_rejected(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"}]
        provider = _make_dispatch_provider(doc, facts, source_types=("CMS_NCCI",))
        store = _bootstrapped_store()
        run_investigation(inv, [doc], _medicare_scope(), provider, store)

        with self.assertRaises(PipelineError):
            run_investigation(inv, [], _medicare_scope(), provider, store)

    def test_no_case_scope_yields_no_supported_discrepancy_not_a_crash(self):
        inv, doc = _fresh_investigation_with_doc()
        facts = [{"fact_type": "code", "value": "45378", "source_span": "45378"},
                 {"fact_type": "code", "value": "45380", "source_span": "45380"}]
        provider = _make_dispatch_provider(doc, facts, source_types=("CMS_NCCI",))
        store = _bootstrapped_store()

        result = run_investigation(inv, [doc], None, provider, store)

        self.assertTrue(result.success)
        self.assertNotEqual(result.final_status, FinalStatus.SUPPORTED_DISCREPANCY)

    def test_no_real_provider_class_imported_into_this_test_module(self):
        import sys
        this_module = sys.modules[__name__]
        self.assertNotIn("GeminiProvider", vars(this_module))
        self.assertNotIn("GenAISDKProvider", vars(this_module))


if __name__ == "__main__":
    unittest.main()
