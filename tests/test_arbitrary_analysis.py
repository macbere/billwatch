from datetime import date
import unittest

from billwatch.arbitrary_analysis import (
    AnalysisContext,
    InputDrivenMockProvider,
    analyze_bill,
    parse_analysis_context,
)
from billwatch.enums import CaseScopeValue
from billwatch.llm_provider import MockLLMProvider
from billwatch.reference_bootstrap import load_bootstrap_data
from billwatch.reference_data import NCCIPairRecord, ReferenceStore


def _store():
    store = ReferenceStore()
    load_bootstrap_data(store)
    return store


def _verified_store(modifier_indicator="0"):
    store = ReferenceStore()
    store.load_snapshot(
        dataset_name="ncci_ptp",
        records=[NCCIPairRecord(
            code_a="45380",
            code_b="45378",
            relationship="column2_bundled_into_column1",
            modifier_indicator=modifier_indicator,
            relationship_verified=True,
            source="CMS NCCI PTP verified test fixture",
            source_url="https://www.cms.gov/",
            effective_date=date(2026, 1, 1),
            version="verified-test-" + modifier_indicator,
            retrieval_date=date(2026, 8, 29),
            license_basis="public_cms_ncci",
            source_file="verified-test.txt",
            source_sha256="0" * 64,
        )],
        source="CMS NCCI PTP verified test fixture",
        source_url="https://www.cms.gov/",
        effective_date=date(2026, 1, 1),
        retrieval_date=date(2026, 8, 29),
        version="verified-test-" + modifier_indicator,
        license_basis="public_cms_ncci",
    )
    return store


class ArbitraryAnalysisTests(unittest.TestCase):
    def test_standard_result_adds_only_backward_compatible_metadata(self):
        result = analyze_bill(
            "Itemized bill: CPT 99213 and CPT 93000.",
            AnalysisContext(),
            InputDrivenMockProvider(),
            _store(),
        )
        output = result.to_dict()
        existing_fields = {
            "success",
            "status",
            "document_id",
            "facts",
            "findings",
            "missing_context",
            "review_note",
            "failure_reason",
            "gemini_mode",
        }
        self.assertTrue(existing_fields.issubset(output))
        self.assertEqual(output["analysis_mode"], "standard")
        self.assertEqual(
            output["completed_stages"],
            [
                "bill_received",
                "facts_extracted",
                "pairs_generated",
                "references_checked",
                "context_evaluated",
            ],
        )
        self.assertNotIn("bill_text", output)

    def test_three_codes_produce_three_unique_pair_findings(self):
        result = analyze_bill(
            "Itemized bill: CPT 45378, CPT 45380, and CPT 99213.",
            AnalysisContext(),
            InputDrivenMockProvider(),
            _store(),
        )

        self.assertTrue(result.success)
        self.assertEqual(
            {(f.code_a, f.code_b) for f in result.findings},
            {("45378", "45380"), ("45378", "99213"), ("45380", "99213")},
        )
        self.assertEqual(result.status, "INSUFFICIENT_CONTEXT")

    def test_unverified_reference_never_becomes_a_potential_error(self):
        result = analyze_bill(
            "Itemized bill: CPT 45378 and CPT 45380 billed on 2026-08-01.",
            AnalysisContext(
                payer_scope=CaseScopeValue.MEDICARE,
                service_date=__import__("datetime").date(2026, 8, 1),
                same_date_confirmed=True,
                same_beneficiary_confirmed=True,
            ),
            InputDrivenMockProvider(),
            _store(),
        )

        self.assertEqual(result.status, "INSUFFICIENT_CONTEXT")
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].status, "REFERENCE_UNVERIFIED")
        self.assertIn("not", result.findings[0].summary.lower())
        self.assertIsNone(result.review_note)
        self.assertEqual(result.missing_context_fields, ())
        self.assertFalse(result.can_resume)
        self.assertTrue(result.blocking_context)
        self.assertIn("verified reference", result.blocking_context[0]["reason"])

    def test_bare_number_requires_billing_line_context(self):
        result = analyze_bill(
            "Claim number 12345\n99213 Office visit $180.00",
            AnalysisContext(),
            InputDrivenMockProvider(),
            _store(),
        )

        self.assertEqual(
            {fact["value"] for fact in result.facts if fact["fact_type"] == "code"},
            {"99213"},
        )

    def test_mixed_numeric_and_alphanumeric_code_shapes_are_extracted(self):
        result = analyze_bill(
            "HCPCS G0471\nCPT 0591T\nCODE 0001A\n45378 diagnostic procedure",
            AnalysisContext(),
            InputDrivenMockProvider(),
            _store(),
        )

        self.assertEqual(
            {fact["value"] for fact in result.facts if fact["fact_type"] == "code"},
            {"G0471", "0591T", "0001A", "45378"},
        )

    def test_unlabeled_account_identifier_is_not_treated_as_code(self):
        result = analyze_bill(
            "Account 0001A\nClaim G0471",
            AnalysisContext(),
            InputDrivenMockProvider(),
            _store(),
        )
        self.assertFalse(
            [fact for fact in result.facts if fact["fact_type"] == "code"]
        )

    def test_private_scope_does_not_apply_medicare_reference_as_controlling(self):
        result = analyze_bill(
            "Itemized bill: CPT 45378 and CPT 45380.",
            AnalysisContext(payer_scope=CaseScopeValue.PRIVATE_COMMERCIAL),
            InputDrivenMockProvider(),
            _store(),
        )

        self.assertEqual(result.status, "INSUFFICIENT_CONTEXT")
        self.assertEqual(result.findings[0].status, "REFERENCE_UNVERIFIED")
        self.assertIn("verified reference", result.findings[0].missing_context[0])

    def test_context_parser_rejects_unknown_scope(self):
        with self.assertRaises(ValueError):
            parse_analysis_context({"payer_scope": "guess_from_bill"})

    def test_no_codes_fails_closed_with_missing_context(self):
        result = analyze_bill(
            "Patient statement: payment due $250.00.",
            AnalysisContext(),
            InputDrivenMockProvider(),
            _store(),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.status, "INSUFFICIENT_CONTEXT")
        self.assertEqual(result.findings, ())
        self.assertIn("billing codes", result.missing_context[0])
        self.assertEqual(
            result.completed_stages,
            (
                "bill_received",
                "facts_extracted",
                "pairs_generated",
                "context_evaluated",
            ),
        )
        self.assertNotIn("references_checked", result.completed_stages)
        self.assertFalse(result.can_resume)
        self.assertTrue(result.blocking_context)

    def test_modifier_indicator_one_requires_modifier_context(self):
        context = AnalysisContext(
            payer_scope=CaseScopeValue.MEDICARE,
            service_date=date(2026, 8, 1),
            same_date_confirmed=True,
            same_beneficiary_confirmed=True,
        )
        result = analyze_bill(
            "CPT 45378 and CPT 45380.",
            context,
            InputDrivenMockProvider(),
            _verified_store("1"),
        )
        self.assertEqual(result.status, "INSUFFICIENT_CONTEXT")
        self.assertEqual(result.findings[0].status, "INSUFFICIENT_CONTEXT")
        self.assertIn("modifier", result.findings[0].missing_context[0])
        self.assertEqual(
            [item["field"] for item in result.missing_context_fields],
            ["modifiers"],
        )
        self.assertTrue(result.can_resume)

    def test_verified_match_structures_only_user_suppliable_context(self):
        result = analyze_bill(
            "CPT 45378 and CPT 45380.",
            AnalysisContext(
                service_date=date(2026, 8, 1),
                same_date_confirmed=True,
                same_beneficiary_confirmed=True,
            ),
            InputDrivenMockProvider(),
            _verified_store("0"),
        )
        self.assertEqual(result.status, "INSUFFICIENT_CONTEXT")
        self.assertEqual(
            [item["field"] for item in result.missing_context_fields],
            ["payer_scope"],
        )
        self.assertEqual(result.blocking_context, ())
        self.assertTrue(result.can_resume)

    def test_outside_effective_period_is_blocking_not_user_correctable(self):
        result = analyze_bill(
            "CPT 45378 and CPT 45380.",
            AnalysisContext(
                payer_scope=CaseScopeValue.MEDICARE,
                service_date=date(2025, 12, 31),
                same_date_confirmed=True,
                same_beneficiary_confirmed=True,
            ),
            InputDrivenMockProvider(),
            _verified_store("0"),
        )
        self.assertEqual(result.status, "INSUFFICIENT_CONTEXT")
        self.assertEqual(result.missing_context_fields, ())
        self.assertFalse(result.can_resume)
        self.assertTrue(result.blocking_context)

    def test_extraction_failure_claims_only_the_completed_bill_received_stage(self):
        result = analyze_bill(
            "CPT 45378 and CPT 45380.",
            AnalysisContext(),
            MockLLMProvider(fixed_response="not json"),
            _store(),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.status, "EXTRACTION_FAILED")
        self.assertEqual(result.completed_stages, ("bill_received",))
        self.assertFalse(result.can_resume)

    def test_pair_expansion_has_a_bounded_input_limit(self):
        bill = " ".join(f"CPT {10000 + index}" for index in range(41))
        result = analyze_bill(
            bill,
            AnalysisContext(),
            InputDrivenMockProvider(),
            _store(),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.status, "INPUT_LIMIT")
        self.assertEqual(result.completed_stages, ("bill_received",))


if __name__ == "__main__":
    unittest.main()
