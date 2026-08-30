"""Safety contract for the isolated public Hackathon Demo rule."""

from dataclasses import replace
from datetime import date
import unittest

from billwatch.arbitrary_analysis import AnalysisContext
from billwatch.enums import CaseScopeValue
from billwatch.reference_bootstrap import PLAN_POLICY_BOOTSTRAP_RECORDS
from billwatch.reference_data import is_ncci_billing_code
import billwatch.synthetic_demo as synthetic_demo


def _complete_context(service_date=date(2026, 8, 1)):
    return AnalysisContext(
        payer_scope=CaseScopeValue.UNKNOWN,
        service_date=service_date,
        same_date_confirmed=True,
        same_beneficiary_confirmed=True,
    )


class SyntheticDemoTests(unittest.TestCase):
    def test_exactly_one_public_rule_is_unmistakably_synthetic(self):
        self.assertEqual(len(synthetic_demo.PUBLIC_SYNTHETIC_RULES), 1)
        rule = synthetic_demo.PUBLIC_SYNTHETIC_RULES[0]
        self.assertEqual(rule.dataset, "billwatch_hackathon_demo")
        self.assertEqual({rule.code_a, rule.code_b}, {"BW-DEMO-001", "BW-DEMO-002"})
        self.assertIn("author-written synthetic", rule.source.lower())
        self.assertEqual(rule.license_basis, "author_written_synthetic_demo")
        self.assertEqual(rule.scope, "billwatch_hackathon_demo_only")
        self.assertTrue(rule.relationship_verified)
        self.assertFalse(is_ncci_billing_code(rule.code_a))
        self.assertFalse(is_ncci_billing_code(rule.code_b))

    def test_recorded_checksum_matches_canonical_rule_content(self):
        rule = synthetic_demo.PUBLIC_SYNTHETIC_RULES[0]
        self.assertEqual(
            synthetic_demo.rule_source_sha256(rule),
            synthetic_demo.PUBLIC_SYNTHETIC_RULE_SOURCE_SHA256,
        )
        self.assertTrue(synthetic_demo.rule_integrity_is_valid(rule))

    def test_exact_demo_mode_is_required_even_for_direct_module_use(self):
        for invalid_mode in (
            None,
            "",
            "HACKATHON_SYNTHETIC_V1",
            "hackathon_synthetic_v1 ",
            True,
            1,
        ):
            with self.subTest(invalid_mode=invalid_mode):
                with self.assertRaises(ValueError):
                    synthetic_demo.analyze_synthetic_bill(
                        synthetic_demo.SYNTHETIC_SAMPLE_BILL,
                        _complete_context(),
                        demo_mode=invalid_mode,
                    )

    def test_exact_identifier_spans_are_extracted_and_ordinary_codes_are_ignored(self):
        source = (
            "Hackathon Demo item\n"
            "Demo identifier BW-DEMO-001 amount $40.00\n"
            "CPT 99213 is ordinary text and must not enter this demo rule\n"
            "Demo identifier BW-DEMO-002 amount $25.00"
        )
        result = synthetic_demo.analyze_synthetic_bill(
            source,
            _complete_context(),
            demo_mode=synthetic_demo.HACKATHON_DEMO_MODE,
        )
        code_facts = [fact for fact in result.facts if fact["fact_type"] == "code"]
        self.assertEqual({fact["value"] for fact in code_facts}, {"BW-DEMO-001", "BW-DEMO-002"})
        self.assertEqual({fact["source_span"] for fact in code_facts}, {"BW-DEMO-001", "BW-DEMO-002"})
        self.assertTrue(all(fact["value"] in fact["source_span"] for fact in code_facts))
        self.assertEqual(len(result.findings), 1)

    def test_near_miss_identifiers_do_not_match(self):
        result = synthetic_demo.analyze_synthetic_bill(
            "BW-DEMO-001X and XBW-DEMO-002",
            _complete_context(),
            demo_mode=synthetic_demo.HACKATHON_DEMO_MODE,
        )
        self.assertEqual(result.facts, ())
        self.assertEqual(result.findings, ())
        self.assertEqual(result.status, "INSUFFICIENT_CONTEXT")
        self.assertIsNone(result.review_note)

    def test_missing_context_pauses_with_exact_evidence_and_reference(self):
        result = synthetic_demo.analyze_synthetic_bill(
            synthetic_demo.SYNTHETIC_SAMPLE_BILL,
            AnalysisContext(),
            demo_mode=synthetic_demo.HACKATHON_DEMO_MODE,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.status, "INSUFFICIENT_CONTEXT")
        self.assertEqual(len(result.facts), 2)
        self.assertEqual(len(result.findings), 1)
        finding = result.findings[0]
        self.assertEqual(finding.status, "INSUFFICIENT_CONTEXT")
        self.assertEqual(len(finding.missing_context), 3)
        self.assertTrue(any("service date" in item.lower() for item in finding.missing_context))
        self.assertTrue(any("same date" in item.lower() for item in finding.missing_context))
        self.assertTrue(any("beneficiary" in item.lower() for item in finding.missing_context))
        self.assertEqual(finding.reference["dataset"], "billwatch_hackathon_demo")
        self.assertTrue(finding.reference["integrity_verified"])
        self.assertIsNone(result.review_note)

    def test_all_deterministic_gates_are_required_for_potential_discrepancy(self):
        result = synthetic_demo.analyze_synthetic_bill(
            synthetic_demo.SYNTHETIC_SAMPLE_BILL,
            _complete_context(),
            demo_mode=synthetic_demo.HACKATHON_DEMO_MODE,
        )
        self.assertEqual(result.status, "POTENTIAL_DISCREPANCY")
        self.assertEqual(result.findings[0].status, "POTENTIAL_DISCREPANCY")
        self.assertIn("not proof", result.findings[0].summary.lower())
        self.assertIsNotNone(result.review_note)
        self.assertIn("not a determination", result.review_note.lower())

    def test_effective_period_failures_fail_closed(self):
        for service_date in (date(2025, 12, 31), date(2027, 1, 1)):
            with self.subTest(service_date=service_date):
                result = synthetic_demo.analyze_synthetic_bill(
                    synthetic_demo.SYNTHETIC_SAMPLE_BILL,
                    _complete_context(service_date),
                    demo_mode=synthetic_demo.HACKATHON_DEMO_MODE,
                )
                self.assertEqual(result.status, "INSUFFICIENT_CONTEXT")
                self.assertEqual(result.findings[0].status, "INSUFFICIENT_CONTEXT")
                self.assertIsNone(result.review_note)

    def test_false_context_confirmation_never_passes_the_gate(self):
        context = replace(_complete_context(), same_date_confirmed=False)
        result = synthetic_demo.analyze_synthetic_bill(
            synthetic_demo.SYNTHETIC_SAMPLE_BILL,
            context,
            demo_mode=synthetic_demo.HACKATHON_DEMO_MODE,
        )
        self.assertEqual(result.status, "INSUFFICIENT_CONTEXT")
        self.assertIsNone(result.review_note)

    def test_tampered_rule_integrity_fails_closed(self):
        original_rules = synthetic_demo.PUBLIC_SYNTHETIC_RULES
        synthetic_demo.PUBLIC_SYNTHETIC_RULES = (
            replace(original_rules[0], source="tampered source"),
        )
        try:
            result = synthetic_demo.analyze_synthetic_bill(
                synthetic_demo.SYNTHETIC_SAMPLE_BILL,
                _complete_context(),
                demo_mode=synthetic_demo.HACKATHON_DEMO_MODE,
            )
        finally:
            synthetic_demo.PUBLIC_SYNTHETIC_RULES = original_rules
        self.assertEqual(result.status, "INSUFFICIENT_CONTEXT")
        self.assertEqual(result.findings[0].status, "REFERENCE_UNVERIFIED")
        self.assertFalse(result.findings[0].reference["integrity_verified"])
        self.assertIsNone(result.review_note)

    def test_repeated_identifiers_still_create_one_unordered_pair(self):
        source = "BW-DEMO-002 BW-DEMO-001 BW-DEMO-002 BW-DEMO-001"
        result = synthetic_demo.analyze_synthetic_bill(
            source,
            _complete_context(),
            demo_mode=synthetic_demo.HACKATHON_DEMO_MODE,
        )
        self.assertEqual(len(result.facts), 2)
        self.assertEqual(len(result.findings), 1)

    def test_deeper_plan_policy_fixture_is_untouched_and_unexposed(self):
        self.assertEqual(len(PLAN_POLICY_BOOTSTRAP_RECORDS), 1)
        fixture = PLAN_POLICY_BOOTSTRAP_RECORDS[0]
        self.assertEqual(fixture.plan_id, "DEMO-PLAN-001")
        self.assertIn("[DEMO FIXTURE", fixture.rule_text)
        self.assertNotIn("BW-DEMO-001", repr(PLAN_POLICY_BOOTSTRAP_RECORDS))
        self.assertNotIn("DEMO-PLAN-001", repr(synthetic_demo.PUBLIC_SYNTHETIC_RULES))


if __name__ == "__main__":
    unittest.main()
