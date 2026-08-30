import unittest

from billwatch import (
    Source,
    SourceType,
    UserContext,
    CaseScope,
    CaseScopeValue,
    ScopeProvenance,
    ValidationResult,
    ClaimType,
    AuthorityResult,
    AuthorityEngineError,
    evaluate_source_authority,
    flag_potential_conflict,
    resolve_case_scope,
    APPROVED_LICENSE_BASES,
)


def _medicare_scope():
    return resolve_case_scope(user_selection="medicare", source_identifier="test")


def _private_scope():
    return resolve_case_scope(user_selection="private", source_identifier="test")


def _unknown_scope():
    return CaseScope(
        value=CaseScopeValue.UNKNOWN,
        provenance=ScopeProvenance.NONE,
        source_identifier="test",
        validation_result=ValidationResult.FAIL,
    )


def _ncci_source():
    return Source(source_type=SourceType.CMS_NCCI, reference="NCCI 45378/45380")


class TestCmsNcciScopeRule(unittest.TestCase):
    """Section 3 / Test-matrix items 1-4: the core scope-conditional rule."""

    def test_1_medicare_plus_applicable_ncci_is_authoritative(self):
        decision = evaluate_source_authority(
            _ncci_source(), _medicare_scope(), ClaimType.CODING_BUNDLING
        )
        self.assertEqual(decision.result, AuthorityResult.AUTHORITATIVE)

    def test_2_private_plan_ncci_without_adoption_evidence_never_controls(self):
        decision = evaluate_source_authority(
            _ncci_source(), _private_scope(), ClaimType.CODING_BUNDLING,
            ncci_adoption_evidence=None,
        )
        self.assertNotEqual(decision.result, AuthorityResult.AUTHORITATIVE)
        self.assertEqual(decision.result, AuthorityResult.CORROBORATING)

    def test_3_private_plan_with_explicit_adoption_evidence_becomes_relevant(self):
        adoption_proof = Source(
            source_type=SourceType.PLAN_POLICY,
            reference="Plan addendum section 4.2: NCCI methodology adopted",
        )
        decision = evaluate_source_authority(
            _ncci_source(), _private_scope(), ClaimType.CODING_BUNDLING,
            ncci_adoption_evidence=adoption_proof,
        )
        self.assertEqual(decision.result, AuthorityResult.AUTHORITATIVE)

    def test_4_unknown_scope_never_guesses(self):
        decision = evaluate_source_authority(
            _ncci_source(), _unknown_scope(), ClaimType.CODING_BUNDLING
        )
        self.assertEqual(decision.result, AuthorityResult.INSUFFICIENT_SCOPE)
        self.assertNotEqual(decision.result, AuthorityResult.AUTHORITATIVE)

    def test_adoption_evidence_must_itself_be_a_plan_policy_source(self):
        bogus_proof = Source(source_type=SourceType.EOB, reference="not a plan policy")
        with self.assertRaises(AuthorityEngineError):
            evaluate_source_authority(
                _ncci_source(), _private_scope(), ClaimType.CODING_BUNDLING,
                ncci_adoption_evidence=bogus_proof,
            )

    def test_adoption_evidence_cannot_be_a_user_context(self):
        uc = UserContext(investigation_id="i", stated_concern_text="my plan adopted NCCI, trust me")
        with self.assertRaises(AuthorityEngineError):
            evaluate_source_authority(
                _ncci_source(), _private_scope(), ClaimType.CODING_BUNDLING,
                ncci_adoption_evidence=uc,
            )

    def test_medicaid_scope_requires_medicaid_specific_reference(self):
        medicaid_scope = resolve_case_scope(user_selection="medicaid", source_identifier="test")
        decision = evaluate_source_authority(
            _ncci_source(), medicaid_scope, ClaimType.CODING_BUNDLING
        )
        self.assertEqual(decision.result, AuthorityResult.OUT_OF_SCOPE)
        self.assertIn("Medicaid-specific", decision.rationale)

    def test_cms_medicare_policy_is_not_medicaid_policy(self):
        source = Source(source_type=SourceType.CMS_MEDICARE, reference="Medicare policy")
        medicaid_scope = resolve_case_scope(user_selection="medicaid", source_identifier="test")
        decision = evaluate_source_authority(
            source, medicaid_scope, ClaimType.COVERAGE_TERMS
        )
        self.assertEqual(decision.result, AuthorityResult.OUT_OF_SCOPE)


class TestScopeConditionalGenerally(unittest.TestCase):
    """Test-matrix items 5-8: conflicting/out-of-scope/applicable/corroborating sources."""

    def test_5_conflicting_scope_indicators_yield_unknown_then_insufficient(self):
        # A CaseScope built from genuinely conflicting indicators resolves
        # to UNKNOWN/FAIL upstream (Build 1); the authority engine must
        # then treat it exactly like any other unresolved scope.
        conflicting = resolve_case_scope(
            user_selection="private", validated_candidate="1AB2-C34-D567",
            source_identifier="conflict",
        )
        self.assertEqual(conflicting.validation_result, ValidationResult.FAIL)
        decision = evaluate_source_authority(
            _ncci_source(), conflicting, ClaimType.CODING_BUNDLING
        )
        self.assertEqual(decision.result, AuthorityResult.INSUFFICIENT_SCOPE)

    def test_6_out_of_scope_source(self):
        medicare_source = Source(source_type=SourceType.CMS_MEDICARE, reference="NCD 123")
        decision = evaluate_source_authority(
            medicare_source, _private_scope(), ClaimType.COVERAGE_TERMS
        )
        self.assertEqual(decision.result, AuthorityResult.OUT_OF_SCOPE)

    def test_7_applicable_source(self):
        plan_source = Source(source_type=SourceType.PLAN_POLICY, reference="Plan doc, section 2")
        decision = evaluate_source_authority(
            plan_source, _private_scope(), ClaimType.COVERAGE_TERMS
        )
        self.assertEqual(decision.result, AuthorityResult.AUTHORITATIVE)

    def test_8_corroborating_source(self):
        decision = evaluate_source_authority(
            _ncci_source(), _private_scope(), ClaimType.CODING_BUNDLING
        )
        self.assertEqual(decision.result, AuthorityResult.CORROBORATING)

    def test_eob_admissible_not_authoritative_for_correctness_claims(self):
        eob_source = Source(source_type=SourceType.EOB, reference="EOB claim #123")
        decision = evaluate_source_authority(
            eob_source, _private_scope(), ClaimType.CODING_BUNDLING
        )
        self.assertEqual(decision.result, AuthorityResult.ADMISSIBLE)

    def test_eob_authoritative_for_adjudication_record_claims(self):
        eob_source = Source(source_type=SourceType.EOB, reference="EOB claim #123")
        decision = evaluate_source_authority(
            eob_source, _private_scope(), ClaimType.ADJUDICATION_RECORD
        )
        self.assertEqual(decision.result, AuthorityResult.AUTHORITATIVE)

    def test_provider_bill_label_never_authoritative(self):
        label_source = Source(source_type=SourceType.PROVIDER_BILL_LABEL, reference="Misc charge")
        decision = evaluate_source_authority(
            label_source, _medicare_scope(), ClaimType.CODING_BUNDLING
        )
        self.assertNotEqual(decision.result, AuthorityResult.AUTHORITATIVE)
        self.assertEqual(decision.result, AuthorityResult.ADMISSIBLE)

    def test_llm_interpretation_is_never_an_evidence_source(self):
        llm_source = Source(source_type=SourceType.LLM_INTERPRETATION, reference="model output")
        decision = evaluate_source_authority(
            llm_source, _medicare_scope(), ClaimType.CODING_BUNDLING
        )
        self.assertEqual(decision.result, AuthorityResult.UNAVAILABLE)

    def test_code_definition_rejects_unlicensed_content(self):
        unlicensed = Source(
            source_type=SourceType.CODE_DEFINITION,
            reference="AMA CPT descriptor text",
            license_usage_basis="unlicensed_ama_cpt_descriptor",
        )
        decision = evaluate_source_authority(unlicensed, _medicare_scope(), ClaimType.DEFINITIONAL)
        self.assertEqual(decision.result, AuthorityResult.UNAVAILABLE)

    def test_code_definition_accepts_approved_license_basis(self):
        for basis in APPROVED_LICENSE_BASES:
            with self.subTest(basis=basis):
                licensed = Source(
                    source_type=SourceType.CODE_DEFINITION,
                    reference="HCPCS Level II descriptor",
                    license_usage_basis=basis,
                )
                decision = evaluate_source_authority(licensed, _medicare_scope(), ClaimType.DEFINITIONAL)
                self.assertEqual(decision.result, AuthorityResult.AUTHORITATIVE)

    def test_public_regulatory_insufficient_scope_when_jurisdiction_unknown(self):
        reg_source = Source(source_type=SourceType.PUBLIC_REGULATORY, reference="State bulletin")
        decision = evaluate_source_authority(reg_source, _private_scope(), ClaimType.JURISDICTIONAL_REGULATORY)
        self.assertEqual(decision.result, AuthorityResult.INSUFFICIENT_SCOPE)


class TestUserAssertionRejectedFromAuthorityPipeline(unittest.TestCase):
    """Test-matrix item 9 -- Gate 2, re-verified at the authority-engine layer."""

    def test_user_assertion_rejected_as_source(self):
        for phrase in (
            "I know they overcharged me.",
            "The hospital definitely billed me twice.",
            "I already proved this is wrong.",
        ):
            with self.subTest(phrase=phrase):
                uc = UserContext(investigation_id="inv-x", stated_concern_text=phrase)
                with self.assertRaises(AuthorityEngineError):
                    evaluate_source_authority(uc, _private_scope(), ClaimType.CODING_BUNDLING)  # type: ignore[arg-type]

    def test_authority_engine_error_is_a_type_error(self):
        # Structural guarantee: callers catching TypeError (as Build 1's
        # Gate 2 tests do) still catch this.
        self.assertTrue(issubclass(AuthorityEngineError, TypeError))


class TestAppealRemainsUnavailable(unittest.TestCase):
    """
    Test-matrix item 10 -- no Build 2 authority decision can directly
    invoke appeal drafting. Build 2 has no appeal-drafting function at all;
    this test documents and locks in that fact so a future build can't
    accidentally wire an AuthorityDecision straight to an appeal without
    going through the Build 1 state-machine Gate 3.
    """

    def test_authority_module_exposes_no_appeal_capability(self):
        import billwatch.authority as authority_module
        forbidden_names = {"draft_appeal", "generate_appeal", "write_appeal", "create_appeal"}
        exposed = set(dir(authority_module))
        self.assertTrue(forbidden_names.isdisjoint(exposed))

    def test_authoritative_decision_alone_does_not_satisfy_gate_3(self):
        from billwatch import InvestigationStateMachine, InvestigationState, FinalStatus, IllegalTransitionError

        decision = evaluate_source_authority(
            _ncci_source(), _medicare_scope(), ClaimType.CODING_BUNDLING
        )
        self.assertEqual(decision.result, AuthorityResult.AUTHORITATIVE)

        # An AUTHORITATIVE *source-level* decision is not the same thing as
        # an investigation-level SUPPORTED_DISCREPANCY final_status. Gate 3
        # is still the only chokepoint, and it still requires the full
        # state machine to reach ADJUDICATED with that specific status.
        sm = InvestigationStateMachine()
        with self.assertRaises(IllegalTransitionError):
            sm.request_draft_appeal()  # state is still INGESTED; unaffected by the decision above


class TestConflictPreparation(unittest.TestCase):
    """Section 8 -- conflicts must be flagged, never silently resolved."""

    def test_two_authoritative_sources_same_claim_flagged_not_resolved(self):
        plan_source = Source(source_type=SourceType.PLAN_POLICY, reference="Plan doc A")
        another_plan_doc = Source(source_type=SourceType.PLAN_POLICY, reference="Plan addendum B")

        decision_a = evaluate_source_authority(plan_source, _private_scope(), ClaimType.COVERAGE_TERMS)
        decision_b = evaluate_source_authority(another_plan_doc, _private_scope(), ClaimType.COVERAGE_TERMS)

        conflict = flag_potential_conflict(decision_a, decision_b)
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.decision_a.source_id, decision_a.source_id)
        self.assertEqual(conflict.decision_b.source_id, decision_b.source_id)
        # Critically: flag_potential_conflict must NOT itself decide who is
        # right -- it returns both decisions unresolved.
        self.assertIn(conflict.decision_a.result, (AuthorityResult.AUTHORITATIVE, AuthorityResult.CORROBORATING))
        self.assertIn(conflict.decision_b.result, (AuthorityResult.AUTHORITATIVE, AuthorityResult.CORROBORATING))

    def test_identical_authoritative_references_do_not_self_conflict(self):
        source_a = Source(source_type=SourceType.PLAN_POLICY, reference="same policy text")
        source_b = Source(source_type=SourceType.PLAN_POLICY, reference="same policy text")
        decision_a = evaluate_source_authority(source_a, _private_scope(), ClaimType.COVERAGE_TERMS)
        decision_b = evaluate_source_authority(source_b, _private_scope(), ClaimType.COVERAGE_TERMS)
        self.assertIsNone(flag_potential_conflict(decision_a, decision_b))

    def test_no_conflict_flagged_across_different_claim_types(self):
        plan_source = Source(source_type=SourceType.PLAN_POLICY, reference="Plan doc A")
        another_plan_doc = Source(source_type=SourceType.PLAN_POLICY, reference="Plan addendum B")
        decision_a = evaluate_source_authority(plan_source, _private_scope(), ClaimType.COVERAGE_TERMS)
        decision_b = evaluate_source_authority(another_plan_doc, _private_scope(), ClaimType.COST_SHARING)
        self.assertIsNone(flag_potential_conflict(decision_a, decision_b))

    def test_no_conflict_when_one_side_out_of_scope(self):
        medicare_source = Source(source_type=SourceType.CMS_MEDICARE, reference="NCD 123")
        plan_source = Source(source_type=SourceType.PLAN_POLICY, reference="Plan doc A")
        decision_a = evaluate_source_authority(medicare_source, _private_scope(), ClaimType.COVERAGE_TERMS)
        decision_b = evaluate_source_authority(plan_source, _private_scope(), ClaimType.COVERAGE_TERMS)
        self.assertEqual(decision_a.result, AuthorityResult.OUT_OF_SCOPE)
        self.assertIsNone(flag_potential_conflict(decision_a, decision_b))


class TestInputTypeGuardsAdversarial(unittest.TestCase):
    """Adversarial tests -- not just happy paths."""

    def test_string_instead_of_source_rejected(self):
        with self.assertRaises(AuthorityEngineError):
            evaluate_source_authority("just a string", _medicare_scope(), ClaimType.CODING_BUNDLING)  # type: ignore[arg-type]

    def test_none_instead_of_case_scope_rejected(self):
        with self.assertRaises(AuthorityEngineError):
            evaluate_source_authority(_ncci_source(), None, ClaimType.CODING_BUNDLING)  # type: ignore[arg-type]

    def test_string_instead_of_claim_type_rejected(self):
        with self.assertRaises(AuthorityEngineError):
            evaluate_source_authority(_ncci_source(), _medicare_scope(), "coding_bundling")  # type: ignore[arg-type]

    def test_decision_is_reproducible_for_identical_inputs(self):
        source = _ncci_source()
        scope = _medicare_scope()
        d1 = evaluate_source_authority(source, scope, ClaimType.CODING_BUNDLING)
        d2 = evaluate_source_authority(source, scope, ClaimType.CODING_BUNDLING)
        self.assertEqual(d1.result, d2.result)
        self.assertEqual(d1.rule_applied, d2.rule_applied)
        self.assertEqual(d1.source_id, d2.source_id)


if __name__ == "__main__":
    unittest.main()
