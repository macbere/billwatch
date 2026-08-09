import unittest

from billwatch import (
    CaseScopeValue,
    ScopeProvenance,
    ValidationResult,
    resolve_case_scope,
)


class TestCaseScopeProvenance(unittest.TestCase):
    """Test B -- CaseScope provenance, the six required cases."""

    def test_case_1_explicit_medicare_selection_passes(self):
        scope = resolve_case_scope(user_selection="medicare", source_identifier="intake")
        self.assertEqual(scope.value, CaseScopeValue.MEDICARE)
        self.assertEqual(scope.provenance, ScopeProvenance.USER_SELECTED)
        self.assertEqual(scope.validation_result, ValidationResult.PASS)

    def test_case_2_explicit_private_plan_selection_passes(self):
        scope = resolve_case_scope(user_selection="private", source_identifier="intake")
        self.assertEqual(scope.value, CaseScopeValue.PRIVATE_COMMERCIAL)
        self.assertEqual(scope.provenance, ScopeProvenance.USER_SELECTED)
        self.assertEqual(scope.validation_result, ValidationResult.PASS)

    def test_case_3_validated_eob_scope_field_passes(self):
        # A deterministically format-matched Medicare-ID-shaped field.
        scope = resolve_case_scope(
            validated_candidate="1AB2-C34-D567", source_identifier="eob_doc_9"
        )
        self.assertEqual(scope.value, CaseScopeValue.MEDICARE)
        self.assertEqual(scope.provenance, ScopeProvenance.VALIDATED_EOB_FIELD)
        self.assertEqual(scope.validation_result, ValidationResult.PASS)

    def test_case_3b_validated_eob_plan_type_vocab_passes(self):
        scope = resolve_case_scope(validated_candidate="PPO", source_identifier="eob_doc_2")
        self.assertEqual(scope.value, CaseScopeValue.PRIVATE_COMMERCIAL)
        self.assertEqual(scope.validation_result, ValidationResult.PASS)

    def test_case_4_llm_only_inference_never_establishes_scope(self):
        scope = resolve_case_scope(
            llm_inferred_guess="This is probably a private commercial plan.",
            source_identifier="llm_guess",
        )
        self.assertEqual(scope.value, CaseScopeValue.UNKNOWN)
        self.assertEqual(scope.provenance, ScopeProvenance.LLM_INFERENCE)
        self.assertEqual(scope.validation_result, ValidationResult.FAIL)

    def test_case_5_conflicting_scope_indicators_fail(self):
        # User says private, but a validated field format-matches Medicare.
        scope = resolve_case_scope(
            user_selection="private",
            validated_candidate="1AB2-C34-D567",
            source_identifier="conflicting",
        )
        self.assertEqual(scope.value, CaseScopeValue.UNKNOWN)
        self.assertEqual(scope.validation_result, ValidationResult.FAIL)

    def test_case_6_no_scope_evidence_fails(self):
        scope = resolve_case_scope(source_identifier="nothing_supplied")
        self.assertEqual(scope.value, CaseScopeValue.UNKNOWN)
        self.assertEqual(scope.validation_result, ValidationResult.FAIL)

    def test_agreeing_user_and_field_scope_passes(self):
        # Sanity check: when user selection and validated field AGREE,
        # scope is established (not treated as a conflict).
        scope = resolve_case_scope(
            user_selection="medicare",
            validated_candidate="1AB2-C34-D567",
            source_identifier="agreeing",
        )
        self.assertEqual(scope.value, CaseScopeValue.MEDICARE)
        self.assertEqual(scope.validation_result, ValidationResult.PASS)

    def test_never_silently_defaults_to_medicare_or_private(self):
        # Explicit regression guard for the exact behavior the TEAM called
        # out: no silent "probably Medicare" / "probably private" default.
        for kwargs in (
            {},
            {"llm_inferred_guess": "probably medicare"},
            {"llm_inferred_guess": "probably private insurance"},
        ):
            scope = resolve_case_scope(source_identifier="guard", **kwargs)
            self.assertEqual(scope.value, CaseScopeValue.UNKNOWN)
            self.assertEqual(scope.validation_result, ValidationResult.FAIL)


if __name__ == "__main__":
    unittest.main()
