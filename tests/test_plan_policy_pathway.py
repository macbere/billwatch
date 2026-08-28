"""
Phase C1: PLAN_POLICY evidence pathway tests.

Covers: lookup success/miss, malformed-record rejection (including the
mandatory demo-fixture marker), provenance/license validation, authority
handling (unchanged, contextual), evidence-ledger entry, UserContext
isolation, domain-decision-smuggling rejection via the existing verification
schema, insufficient-evidence routing, a duplicate-source non-conflict
adversarial case, full-pipeline SUPPORTED_DISCREPANCY reachability, and
Gate 3 appeal gating -- all via the real, unmodified pipeline machinery.
"""
import json
import re
import unittest
from datetime import date

from billwatch import Document, Investigation
from billwatch.case_scope import establish_from_user_selection
from billwatch.enums import SourceType
from billwatch.evidence import ExtractedFact
from billwatch.llm_provider import MockLLMProvider, LLMProviderError
from billwatch.reference_bootstrap import load_bootstrap_data
from billwatch.reference_data import (
    ReferenceStore, PlanPolicyRecord, PLAN_POLICY_LICENSE_BASIS,
    validate_plan_policy_record, LookupStatus,
)
from billwatch.authority import evaluate_source_authority, ClaimType, AuthorityResult, flag_potential_conflict
from billwatch.pipeline import run_investigation
from billwatch.user_context import UserContext


def _fresh_store():
    store = ReferenceStore()
    load_bootstrap_data(store)
    return store


class TestPlanPolicyRecordValidation(unittest.TestCase):
    def _valid_record(self, **overrides):
        base = dict(
            plan_id="DEMO-PLAN-001", policy_id="DEMO-POL-999",
            rule_type="coverage_rule",
            rule_text="[DEMO FIXTURE -- synthetic] some rule text",
            applicable_codes=("Z00.00",),
            patient_cost_share_cents=0,
            source="s", source_url="u", effective_date=date(2026, 1, 1),
            version="v1", retrieval_date=date(2026, 1, 1),
            license_basis=PLAN_POLICY_LICENSE_BASIS,
        )
        base.update(overrides)
        return PlanPolicyRecord(**base)

    def test_valid_record_passes(self):
        self.assertEqual(validate_plan_policy_record(self._valid_record()), [])

    def test_missing_demo_marker_rejected(self):
        rec = self._valid_record(rule_text="This looks like a real policy statement.")
        issues = validate_plan_policy_record(rec)
        self.assertTrue(any("demo-fixture marker" in i for i in issues))

    def test_public_cms_license_basis_rejected_for_plan_policy(self):
        # Confirms plan-policy data cannot masquerade as public CMS data.
        rec = self._valid_record(license_basis="public_domain_cms")
        issues = validate_plan_policy_record(rec)
        self.assertTrue(any("license_basis" in i for i in issues))

    def test_malformed_plan_id_rejected(self):
        rec = self._valid_record(plan_id="!!bad!!")
        issues = validate_plan_policy_record(rec)
        self.assertTrue(any("malformed plan_id" in i for i in issues))

    def test_negative_patient_cost_share_rejected(self):
        rec = self._valid_record(patient_cost_share_cents=-1)
        issues = validate_plan_policy_record(rec)
        self.assertTrue(any(
            "patient_cost_share_cents" in issue
            for issue in issues
        ))

    def test_boolean_patient_cost_share_rejected(self):
        rec = self._valid_record(patient_cost_share_cents=True)
        issues = validate_plan_policy_record(rec)
        self.assertTrue(any(
            "patient_cost_share_cents" in issue
            for issue in issues
        ))

    def test_unrecognized_rule_type_rejected(self):
        rec = self._valid_record(rule_type="not_a_real_type")
        issues = validate_plan_policy_record(rec)
        self.assertTrue(any("unrecognized rule_type" in i for i in issues))


class TestPlanPolicyLookup(unittest.TestCase):
    def test_bootstrap_plan_policy_loads_cleanly(self):
        store = _fresh_store()
        snapshot = store.get_current_snapshot("plan_policy")
        self.assertIsNotNone(snapshot)
        self.assertEqual(len(snapshot.records), 1)

    def test_lookup_known_plan_id_found(self):
        store = _fresh_store()
        result = store.lookup_plan_policy("DEMO-PLAN-001")
        self.assertEqual(result.status, LookupStatus.FOUND)

    def test_lookup_unknown_plan_id_returns_unknown(self):
        store = _fresh_store()
        result = store.lookup_plan_policy("NOT-A-REAL-PLAN")
        self.assertEqual(result.status, LookupStatus.UNKNOWN)

    def test_to_source_produces_plan_policy_source_type(self):
        store = _fresh_store()
        result = store.lookup_plan_policy("DEMO-PLAN-001")
        source = store.to_source(result)
        self.assertEqual(source.source_type, SourceType.PLAN_POLICY)
        self.assertEqual(source.license_usage_basis, PLAN_POLICY_LICENSE_BASIS)


class TestPlanPolicyAuthorityUnchanged(unittest.TestCase):
    """Confirms authority.py's existing, unmodified PLAN_POLICY rule --
    authoritative for a plan's own terms regardless of case scope."""

    def test_plan_policy_authoritative_regardless_of_scope(self):
        from billwatch.case_scope import CaseScope, ScopeProvenance
        from billwatch.enums import CaseScopeValue, ValidationResult

        store = _fresh_store()
        source = store.to_source(store.lookup_plan_policy("DEMO-PLAN-001"))
        unresolved_scope = CaseScope(
            value=CaseScopeValue.UNKNOWN, provenance=ScopeProvenance.NONE,
            source_identifier="test", validation_result=ValidationResult.FAIL,
        )
        decision = evaluate_source_authority(source, unresolved_scope, ClaimType.GENERIC)
        self.assertEqual(decision.result, AuthorityResult.AUTHORITATIVE)

    def test_duplicate_plan_policy_decision_does_not_self_conflict(self):
        store = _fresh_store()
        source = store.to_source(store.lookup_plan_policy("DEMO-PLAN-001"))
        from billwatch.case_scope import establish_from_user_selection
        scope = establish_from_user_selection("medicare")
        d1 = evaluate_source_authority(source, scope, ClaimType.GENERIC)
        d2 = evaluate_source_authority(source, scope, ClaimType.GENERIC)
        # Same source_id -> flag_potential_conflict must return None.
        self.assertIsNone(flag_potential_conflict(d1, d2))


class TestPlanPolicyEndToEnd(unittest.TestCase):
    """Full pipeline via run_investigation(), mock provider, real
    deterministic lookups -- no fixture shortcuts."""

    def _mock_provider_for_plan_policy(self, doc):
        def dispatch(system_prompt, user_content):
            if "document-extraction component" in system_prompt:
                facts = []

                if "DEMO-PLAN-001" in doc.raw_text:
                    facts.append({
                        "fact_type": "clause",
                        "value": "DEMO-PLAN-001",
                        "source_span": "DEMO-PLAN-001",
                    })

                if "Z00.00" in doc.raw_text:
                    facts.append({
                        "fact_type": "code",
                        "value": "Z00.00",
                        "source_span": "Z00.00",
                    })

                for date_match in re.finditer(
                    r"\b\d{4}-\d{2}-\d{2}\b",
                    doc.raw_text,
                ):
                    literal_date = date_match.group(0)
                    facts.append({
                        "fact_type": "date",
                        "value": literal_date,
                        "source_span": literal_date,
                    })

                amount_match = re.search(
                    r"Patient responsibility:\s*\$([0-9]+(?:\.[0-9]{1,2})?)",
                    doc.raw_text,
                    re.IGNORECASE,
                )
                if amount_match:
                    literal = amount_match.group(0)
                    facts.append({
                        "fact_type": "amount",
                        "value": amount_match.group(1),
                        "source_span": literal,
                    })

                return json.dumps({
                    "document_id": doc.id,
                    "extracted_facts": facts,
                })
            if "hypothesis-proposal component" in system_prompt:
                fact_ids = re.findall(r"fact_id=([0-9a-fA-F-]+)", user_content)
                return json.dumps({
                    "claim_statement": "Possible coverage policy discrepancy",
                    "explanation_text": "Plan identifier and code found together.",
                    "referenced_fact_ids": fact_ids,
                })
            if "verification-planning component" in system_prompt:
                m = re.search(r"hypothesis_id:\s*(\S+)", user_content)
                return json.dumps({
                    "hypothesis_id": m.group(1) if m else "",
                    "proposed_source_types": ["PLAN_POLICY"],
                    "verification_rationale": "Check plan policy coverage rule.",
                })
            if "appeal-drafting component" in system_prompt:
                m = re.search(r"claim_id:\s*(\S+)", user_content)
                fact_ids = re.findall(r"fact_id=([0-9a-fA-F-]+)", user_content)
                return json.dumps({
                    "draft_text": "This is a request for human review of the plan-policy coverage question raised by this claim.",
                    "cited_fact_ids": fact_ids,
                    "cited_claim_ids": [m.group(1)] if m else [],
                })
            return "{}"
        return MockLLMProvider(response_fn=dispatch)

    def _run(self, doc_text, case_scope):
        doc = Document(doc_type="bill", raw_text=doc_text)
        provider = self._mock_provider_for_plan_policy(doc)
        investigation = Investigation()
        store = _fresh_store()
        return run_investigation(investigation, [doc], case_scope, provider, store), investigation

    def test_supported_discrepancy_reachable_via_plan_policy(self):
        scope = establish_from_user_selection("medicare")
        result, investigation = self._run(
            "Bill references plan DEMO-PLAN-001 and code Z00.00. "
            "Service date: 2026-06-15. "
            "Patient responsibility: $75.00",
            scope,
        )
        self.assertTrue(result.success, result.failure_reason if not result.success else None)
        self.assertEqual(result.final_status.value, "supported_discrepancy")
        self.assertIsNotNone(result.appeal)
        self.assertTrue(result.appeal.success)
        self.assertIsNotNone(result.appeal.draft_text)
        # Confirm real Verification entered the ledger with the right source type.
        self.assertTrue(any(v.authority_result == "authoritative" for v in investigation.ledger.verifications))

    def test_missing_plan_id_yields_insufficient_evidence_no_appeal(self):
        scope = establish_from_user_selection("medicare")
        result, investigation = self._run(
            "Bill references code Z00.00 with no plan identifier at all. "
            "Service date: 2026-06-15.", scope,
        )
        # No 'clause' fact will match a known plan_id -> MissingEvidence -> UNCHECKED -> INSUFFICIENT_EVIDENCE.
        self.assertTrue(result.success)
        self.assertNotEqual(result.final_status.value, "supported_discrepancy")
        self.assertFalse(result.appeal.success if result.appeal else False)

    def test_matching_zero_cost_share_is_checked_clean_no_appeal(self):
        scope = establish_from_user_selection("medicare")
        result, investigation = self._run(
            "Bill references plan DEMO-PLAN-001 and code Z00.00. "
            "Service date: 2026-06-15. "
            "Patient responsibility: $0.00",
            scope,
        )
        self.assertTrue(result.success)
        self.assertEqual(
            result.final_status.value,
            "no_supported_discrepancy",
        )
        self.assertFalse(result.appeal.success if result.appeal else False)

        matching = [
            v for v in investigation.ledger.verifications
            if v.authority_result == "authoritative"
        ]
        self.assertTrue(matching)
        self.assertTrue(all(
            v.corroboration_result == "silent"
            for v in matching
        ))

    def test_policy_exists_but_missing_patient_amount_is_not_supported(self):
        scope = establish_from_user_selection("medicare")
        result, investigation = self._run(
            "Bill references plan DEMO-PLAN-001 and code Z00.00. "
            "Service date: 2026-06-15.",
            scope,
        )
        self.assertTrue(result.success)
        self.assertEqual(
            result.final_status.value,
            "insufficient_evidence",
        )
        self.assertFalse(result.appeal.success if result.appeal else False)

    def test_wrong_code_cannot_be_supported_by_unrelated_policy(self):
        doc = Document(
            doc_type="bill",
            raw_text=(
                "Bill references plan DEMO-PLAN-001 and code A0425. "
                "Service date: 2026-06-15. "
                "Patient responsibility: $75.00"
            ),
        )

        def dispatch(system_prompt, user_content):
            if "document-extraction component" in system_prompt:
                return json.dumps({
                    "document_id": doc.id,
                    "extracted_facts": [
                        {
                            "fact_type": "clause",
                            "value": "DEMO-PLAN-001",
                            "source_span": "DEMO-PLAN-001",
                        },
                        {
                            "fact_type": "code",
                            "value": "A0425",
                            "source_span": "A0425",
                        },
                        {
                            "fact_type": "amount",
                            "value": "75.00",
                            "source_span": "Patient responsibility: $75.00",
                        },
                    ],
                })
            if "hypothesis-proposal component" in system_prompt:
                fact_ids = re.findall(
                    r"fact_id=([0-9a-fA-F-]+)",
                    user_content,
                )
                return json.dumps({
                    "claim_statement":
                        "Possible coverage policy discrepancy",
                    "explanation_text":
                        "Plan, code and patient amount found.",
                    "referenced_fact_ids": fact_ids,
                })
            if "verification-planning component" in system_prompt:
                m = re.search(
                    r"hypothesis_id:\s*(\S+)",
                    user_content,
                )
                return json.dumps({
                    "hypothesis_id": m.group(1) if m else "",
                    "proposed_source_types": ["PLAN_POLICY"],
                    "verification_rationale":
                        "Check policy applicability.",
                })
            return "{}"

        provider = MockLLMProvider(response_fn=dispatch)
        investigation = Investigation()
        store = _fresh_store()

        result = run_investigation(
            investigation,
            [doc],
            establish_from_user_selection("medicare"),
            provider,
            store,
        )

        self.assertTrue(result.success)
        self.assertEqual(
            result.final_status.value,
            "insufficient_evidence",
        )
        self.assertFalse(result.appeal.success if result.appeal else False)

    def test_generic_bill_total_does_not_masquerade_as_patient_responsibility(self):
        doc = Document(
            doc_type="bill",
            raw_text=(
                "Bill references plan DEMO-PLAN-001 and code Z00.00. "
                "Total charges: $75.00"
            ),
        )

        def dispatch(system_prompt, user_content):
            if "document-extraction component" in system_prompt:
                return json.dumps({
                    "document_id": doc.id,
                    "extracted_facts": [
                        {
                            "fact_type": "clause",
                            "value": "DEMO-PLAN-001",
                            "source_span": "DEMO-PLAN-001",
                        },
                        {
                            "fact_type": "code",
                            "value": "Z00.00",
                            "source_span": "Z00.00",
                        },
                        {
                            "fact_type": "amount",
                            "value": "75.00",
                            "source_span": "Total charges: $75.00",
                        },
                    ],
                })
            if "hypothesis-proposal component" in system_prompt:
                ids = re.findall(
                    r"fact_id=([0-9a-fA-F-]+)",
                    user_content,
                )
                return json.dumps({
                    "claim_statement":
                        "Possible coverage policy discrepancy",
                    "explanation_text":
                        "Generic charge found.",
                    "referenced_fact_ids": ids,
                })
            if "verification-planning component" in system_prompt:
                m = re.search(
                    r"hypothesis_id:\s*(\S+)",
                    user_content,
                )
                return json.dumps({
                    "hypothesis_id": m.group(1) if m else "",
                    "proposed_source_types": ["PLAN_POLICY"],
                    "verification_rationale":
                        "Check policy.",
                })
            return "{}"

        investigation = Investigation()
        result = run_investigation(
            investigation,
            [doc],
            establish_from_user_selection("medicare"),
            MockLLMProvider(response_fn=dispatch),
            _fresh_store(),
        )

        self.assertTrue(result.success)
        self.assertEqual(
            result.final_status.value,
            "insufficient_evidence",
        )
        self.assertFalse(result.appeal.success if result.appeal else False)

    def test_two_patient_responsibility_amounts_are_ambiguous_and_fail_closed(self):
        doc = Document(
            doc_type="bill",
            raw_text=(
                "Bill references plan DEMO-PLAN-001 and code Z00.00. "
                "Patient responsibility: $75.00. "
                "Patient responsibility: $25.00"
            ),
        )

        def dispatch(system_prompt, user_content):
            if "document-extraction component" in system_prompt:
                return json.dumps({
                    "document_id": doc.id,
                    "extracted_facts": [
                        {
                            "fact_type": "clause",
                            "value": "DEMO-PLAN-001",
                            "source_span": "DEMO-PLAN-001",
                        },
                        {
                            "fact_type": "code",
                            "value": "Z00.00",
                            "source_span": "Z00.00",
                        },
                        {
                            "fact_type": "amount",
                            "value": "75.00",
                            "source_span":
                                "Patient responsibility: $75.00",
                        },
                        {
                            "fact_type": "amount",
                            "value": "25.00",
                            "source_span":
                                "Patient responsibility: $25.00",
                        },
                    ],
                })
            if "hypothesis-proposal component" in system_prompt:
                ids = re.findall(
                    r"fact_id=([0-9a-fA-F-]+)",
                    user_content,
                )
                return json.dumps({
                    "claim_statement":
                        "Possible coverage policy discrepancy",
                    "explanation_text":
                        "Multiple amounts require resolution.",
                    "referenced_fact_ids": ids,
                })
            if "verification-planning component" in system_prompt:
                m = re.search(
                    r"hypothesis_id:\s*(\S+)",
                    user_content,
                )
                return json.dumps({
                    "hypothesis_id": m.group(1) if m else "",
                    "proposed_source_types": ["PLAN_POLICY"],
                    "verification_rationale":
                        "Check policy.",
                })
            return "{}"

        investigation = Investigation()
        result = run_investigation(
            investigation,
            [doc],
            establish_from_user_selection("medicare"),
            MockLLMProvider(response_fn=dispatch),
            _fresh_store(),
        )

        self.assertTrue(result.success)
        self.assertEqual(
            result.final_status.value,
            "insufficient_evidence",
        )
        self.assertFalse(result.appeal.success if result.appeal else False)

    def test_missing_service_date_fails_closed(self):
        scope = establish_from_user_selection("medicare")
        result, investigation = self._run(
            "Bill references plan DEMO-PLAN-001 and code Z00.00. "
            "Patient responsibility: $75.00",
            scope,
        )
        self.assertTrue(result.success)
        self.assertEqual(
            result.final_status.value,
            "insufficient_evidence",
        )
        self.assertFalse(result.appeal.success if result.appeal else False)

    def test_policy_not_yet_effective_on_service_date_fails_closed(self):
        scope = establish_from_user_selection("medicare")
        result, investigation = self._run(
            "Bill references plan DEMO-PLAN-001 and code Z00.00. "
            "Service date: 2025-12-31. "
            "Patient responsibility: $75.00",
            scope,
        )
        self.assertTrue(result.success)
        self.assertEqual(
            result.final_status.value,
            "insufficient_evidence",
        )
        self.assertFalse(result.appeal.success if result.appeal else False)

    def test_policy_effective_date_boundary_is_accepted(self):
        scope = establish_from_user_selection("medicare")
        result, investigation = self._run(
            "Bill references plan DEMO-PLAN-001 and code Z00.00. "
            "Service date: 2026-01-01. "
            "Patient responsibility: $75.00",
            scope,
        )
        self.assertTrue(result.success)
        self.assertEqual(
            result.final_status.value,
            "supported_discrepancy",
        )
        self.assertIsNotNone(result.appeal)
        self.assertTrue(result.appeal.success)

    def test_two_distinct_service_dates_are_ambiguous_and_fail_closed(self):
        scope = establish_from_user_selection("medicare")
        result, investigation = self._run(
            "Bill references plan DEMO-PLAN-001 and code Z00.00. "
            "Service dates: 2026-06-15 and 2026-06-16. "
            "Patient responsibility: $75.00",
            scope,
        )
        self.assertTrue(result.success)
        self.assertEqual(
            result.final_status.value,
            "insufficient_evidence",
        )
        self.assertFalse(result.appeal.success if result.appeal else False)

    def test_malformed_date_does_not_establish_temporal_applicability(self):
        scope = establish_from_user_selection("medicare")
        result, investigation = self._run(
            "Bill references plan DEMO-PLAN-001 and code Z00.00. "
            "Service date: 06/15/2026. "
            "Patient responsibility: $75.00",
            scope,
        )
        self.assertTrue(result.success)
        self.assertEqual(
            result.final_status.value,
            "insufficient_evidence",
        )
        self.assertFalse(result.appeal.success if result.appeal else False)

    def test_plan_policy_cannot_support_discrepancy_with_unresolved_scope(self):
        result, investigation = self._run(
            "Bill references plan DEMO-PLAN-001 and code Z00.00. "
            "Service date: 2026-06-15. "
            "Patient responsibility: $75.00",
            None,
        )

        self.assertTrue(result.success)

        # The plan-policy lookup may genuinely corroborate the hypothesis,
        # but Gate 1 remains independent: unresolved case scope cannot
        # produce SUPPORTED_DISCREPANCY.
        self.assertNotEqual(
            result.final_status.value,
            "supported_discrepancy",
        )

        self.assertEqual(
            result.final_status.value,
            "no_supported_discrepancy",
        )

        self.assertFalse(
            result.appeal.success if result.appeal else False
        )

        self.assertTrue(
            any(
                v.corroboration_result == "corroborated"
                for v in investigation.ledger.verifications
            )
        )

    def test_user_context_cannot_enter_plan_policy_evidence_path(self):
        scope = establish_from_user_selection("medicare")
        doc = Document(doc_type="bill", raw_text="Bill references plan DEMO-PLAN-001.")
        investigation = Investigation()
        uc = UserContext(investigation_id=investigation.investigation_id, stated_concern_text="I know my plan covers this")
        with self.assertRaises(TypeError):
            investigation.ledger.add_source(uc)

    def test_verification_candidate_smuggled_domain_field_still_rejected(self):
        from billwatch.llm_schemas import SchemaValidationError, parse_verification_candidate
        raw = json.dumps({
            "hypothesis_id": "whatever",
            "proposed_source_types": ["PLAN_POLICY"],
            "verification_rationale": "check",
            "final_status": "supported_discrepancy",
        })
        with self.assertRaises(SchemaValidationError):
            parse_verification_candidate(raw, known_hypothesis_ids={"whatever"})


if __name__ == "__main__":
    unittest.main()
