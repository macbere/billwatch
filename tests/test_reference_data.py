import unittest
from datetime import date

from billwatch import (
    ReferenceStore,
    ReferenceDataError,
    LookupStatus,
    HCPCSRecord,
    ICD10Record,
    NCCIPairRecord,
    evaluate_source_authority,
    ClaimType,
    AuthorityResult,
    resolve_case_scope,
)
from billwatch.reference_bootstrap import load_bootstrap_data

_VALID_KW = dict(
    source="CMS HCPCS Level II Quarterly Update (public use file)",
    source_url="https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update",
    effective_date=date(2026, 1, 1),
    version="2026-Q1-illustrative",
    retrieval_date=date(2026, 8, 9),
    license_basis="public_domain_cms",
)


def _hcpcs(code="A0425", **overrides):
    kw = dict(code=code, description="Ground mileage, per statute mile",
              description_verified=False, **_VALID_KW)
    kw.update(overrides)
    return HCPCSRecord(**kw)


def _bootstrapped_store() -> ReferenceStore:
    store = ReferenceStore()
    load_bootstrap_data(store)
    return store


class TestHCPCSLookup(unittest.TestCase):
    """1. HCPCS known lookup / 2. HCPCS unknown lookup."""

    def test_1_known_hcpcs_code_found(self):
        store = _bootstrapped_store()
        result = store.lookup_hcpcs("A0425")
        self.assertEqual(result.status, LookupStatus.FOUND)
        self.assertEqual(result.record.code, "A0425")

    def test_2_unknown_hcpcs_code_returns_unknown_not_a_guess(self):
        store = _bootstrapped_store()
        result = store.lookup_hcpcs("Z9999")
        self.assertEqual(result.status, LookupStatus.UNKNOWN)
        self.assertIsNone(result.record)


class TestICD10Lookup(unittest.TestCase):
    """3. ICD-10 known lookup / 4. ICD-10 unknown lookup."""

    def test_3_known_icd10_code_found(self):
        store = _bootstrapped_store()
        result = store.lookup_icd10("Z00.00")
        self.assertEqual(result.status, LookupStatus.FOUND)

    def test_4_unknown_icd10_code_returns_unknown(self):
        store = _bootstrapped_store()
        result = store.lookup_icd10("Q99.99")
        self.assertEqual(result.status, LookupStatus.UNKNOWN)
        self.assertIsNone(result.record)


class TestNCCIPairLookup(unittest.TestCase):
    """5. NCCI applicable pair / 6. NCCI non-applicable pair."""

    def test_5_applicable_ncci_pair_found(self):
        store = _bootstrapped_store()
        result = store.lookup_ncci_pair("45378", "45380")
        self.assertEqual(result.status, LookupStatus.FOUND)
        self.assertEqual(result.record.relationship, "column2_bundled_into_column1")

    def test_5b_order_independent(self):
        store = _bootstrapped_store()
        result = store.lookup_ncci_pair("45380", "45378")
        self.assertEqual(result.status, LookupStatus.FOUND)

    def test_6_non_applicable_pair_returns_unknown(self):
        store = _bootstrapped_store()
        result = store.lookup_ncci_pair("99213", "99214")
        self.assertEqual(result.status, LookupStatus.UNKNOWN)


class TestMalformedAndInvalidRecords(unittest.TestCase):
    """7. malformed reference record / 8. missing provenance / 9. unsupported license basis."""

    def test_7_malformed_code_format_rejected(self):
        store = ReferenceStore()
        bad = _hcpcs(code="NOTVALID")
        # malformed record alone with nothing else valid -> whole snapshot rejected
        with self.assertRaises(ReferenceDataError):
            store.load_snapshot(dataset_name="hcpcs", records=[bad], **_VALID_KW)

    def test_7b_malformed_record_excluded_when_valid_records_also_present(self):
        store = ReferenceStore()
        good = _hcpcs(code="A0425")
        bad = _hcpcs(code="BADCODE!")
        snapshot, rejections = store.load_snapshot(
            dataset_name="hcpcs", records=[good, bad], **_VALID_KW
        )
        self.assertEqual(len(snapshot.records), 1)
        self.assertEqual(snapshot.records[0].code, "A0425")
        self.assertEqual(len(rejections), 1)
        self.assertIn("BADCODE!", rejections[0].record_ref)

    def test_8_missing_provenance_rejected(self):
        store = ReferenceStore()
        kw = dict(_VALID_KW)
        kw["source"] = ""  # missing source at snapshot level
        with self.assertRaises(ReferenceDataError):
            store.load_snapshot(dataset_name="hcpcs", records=[_hcpcs()], **kw)

    def test_8b_missing_record_level_provenance_rejected(self):
        store = ReferenceStore()
        record_missing_url = _hcpcs(source_url="")
        with self.assertRaises(ReferenceDataError):
            store.load_snapshot(dataset_name="hcpcs", records=[record_missing_url], **_VALID_KW)

    def test_9_unsupported_license_basis_rejected(self):
        store = ReferenceStore()
        kw = dict(_VALID_KW)
        kw["license_basis"] = "unlicensed_ama_cpt_descriptor"
        with self.assertRaises(ReferenceDataError):
            store.load_snapshot(dataset_name="hcpcs", records=[_hcpcs(license_basis=kw["license_basis"])], **kw)

    def test_9b_missing_license_basis_rejected_not_warned(self):
        # Fail-closed: an empty/unrecognized license_basis is REJECTED, never
        # merely warned about and accepted anyway.
        store = ReferenceStore()
        with self.assertRaises(ReferenceDataError):
            store.load_snapshot(
                dataset_name="hcpcs", records=[_hcpcs(license_basis="")],
                source=_VALID_KW["source"], source_url=_VALID_KW["source_url"],
                effective_date=_VALID_KW["effective_date"], version=_VALID_KW["version"],
                retrieval_date=_VALID_KW["retrieval_date"], license_basis="",
            )

    def test_duplicate_records_within_a_snapshot_are_excluded(self):
        store = ReferenceStore()
        dup1 = _hcpcs(code="A0425")
        dup2 = _hcpcs(code="A0425")  # same code, different object/id
        snapshot, rejections = store.load_snapshot(
            dataset_name="hcpcs", records=[dup1, dup2], **_VALID_KW
        )
        self.assertEqual(len(snapshot.records), 1)
        self.assertEqual(len(rejections), 1)
        self.assertIn("duplicate", rejections[0].reason)


class TestEffectiveDateHandling(unittest.TestCase):
    """10. effective-date handling."""

    def test_10_record_outside_effective_period_not_automatically_applicable(self):
        store = ReferenceStore()
        future = _hcpcs(code="A0425", effective_date=date(2099, 1, 1))
        store.load_snapshot(dataset_name="hcpcs", records=[future], **_VALID_KW)
        result = store.lookup_hcpcs("A0425", as_of=date(2026, 1, 1))
        self.assertEqual(result.status, LookupStatus.OUTSIDE_EFFECTIVE_PERIOD)

    def test_10b_record_within_effective_period_found(self):
        store = _bootstrapped_store()
        result = store.lookup_hcpcs("A0425", as_of=date(2026, 12, 31))
        self.assertEqual(result.status, LookupStatus.FOUND)


class TestSnapshotImmutabilityAndVersioning(unittest.TestCase):
    """11. reference snapshot immutability."""

    def test_11_cannot_reload_same_version(self):
        store = ReferenceStore()
        store.load_snapshot(dataset_name="hcpcs", records=[_hcpcs()], **_VALID_KW)
        with self.assertRaises(ReferenceDataError):
            store.load_snapshot(dataset_name="hcpcs", records=[_hcpcs()], **_VALID_KW)

    def test_11b_new_version_does_not_remove_old_version(self):
        store = ReferenceStore()
        store.load_snapshot(dataset_name="hcpcs", records=[_hcpcs()], **_VALID_KW)
        kw2 = dict(_VALID_KW)
        kw2["version"] = "2026-Q2-illustrative"
        store.load_snapshot(dataset_name="hcpcs", records=[_hcpcs()], **kw2)
        self.assertEqual(
            set(store.all_versions("hcpcs")),
            {"2026-Q1-illustrative", "2026-Q2-illustrative"},
        )
        # Old version is still independently retrievable.
        old = store.get_snapshot_version("hcpcs", "2026-Q1-illustrative")
        self.assertIsNotNone(old)

    def test_11c_snapshot_dataclass_is_frozen(self):
        import dataclasses
        store = ReferenceStore()
        snapshot, _ = store.load_snapshot(dataset_name="hcpcs", records=[_hcpcs()], **_VALID_KW)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            snapshot.version = "tampered"


class TestProvenancePreservation(unittest.TestCase):
    """12. provenance preservation."""

    def test_12_lookup_result_traces_back_to_full_provenance(self):
        store = _bootstrapped_store()
        result = store.lookup_hcpcs("A0425")
        rec = result.record
        self.assertTrue(rec.source)
        self.assertTrue(rec.source_url)
        self.assertIsInstance(rec.effective_date, date)
        self.assertTrue(rec.version)
        self.assertIsInstance(rec.retrieval_date, date)
        self.assertTrue(rec.license_basis)


class TestScopeAwareAuthorityIntegration(unittest.TestCase):
    """13. scope-aware authority integration / 14. lookup success != authoritative."""

    def test_13_found_ncci_lookup_converts_to_source_and_still_needs_gate_1(self):
        store = _bootstrapped_store()
        lookup = store.lookup_ncci_pair("45378", "45380")
        self.assertEqual(lookup.status, LookupStatus.FOUND)
        source = store.to_source(lookup)
        self.assertIsNotNone(source)

        medicare_scope = resolve_case_scope(user_selection="medicare", source_identifier="t")
        decision = evaluate_source_authority(source, medicare_scope, ClaimType.CODING_BUNDLING)
        self.assertEqual(decision.result, AuthorityResult.AUTHORITATIVE)

    def test_14_ncci_lookup_success_does_not_auto_become_authoritative_for_private_plan(self):
        """
        THE key regression this build must never introduce: a successful
        reference lookup is not itself an authority decision. Private-plan
        scope with no adoption evidence must still yield CORROBORATING, even
        though the NCCI pair was found in the reference store.
        """
        store = _bootstrapped_store()
        lookup = store.lookup_ncci_pair("45378", "45380")
        source = store.to_source(lookup)

        private_scope = resolve_case_scope(user_selection="private", source_identifier="t")
        decision = evaluate_source_authority(
            source, private_scope, ClaimType.CODING_BUNDLING, ncci_adoption_evidence=None
        )
        self.assertNotEqual(decision.result, AuthorityResult.AUTHORITATIVE)
        self.assertEqual(decision.result, AuthorityResult.CORROBORATING)

    def test_unfound_lookup_yields_no_source_at_all(self):
        store = _bootstrapped_store()
        lookup = store.lookup_hcpcs("Z9999")
        self.assertIsNone(store.to_source(lookup))


class TestCPTDescriptorBoundary(unittest.TestCase):
    """15. CPT descriptor request routes to unavailable, never invented content."""

    def test_15_cpt_descriptor_always_unavailable(self):
        store = _bootstrapped_store()
        for code in ("45378", "45380", "99999", ""):
            with self.subTest(code=code):
                result = store.lookup_cpt_descriptor(code)
                self.assertEqual(result.status, LookupStatus.UNAVAILABLE)
                self.assertIsNone(result.record)

    def test_15b_cpt_lookup_never_consults_any_snapshot(self):
        # Even if a store somehow had NCCI records referencing these exact
        # CPT numbers, lookup_cpt_descriptor must not return their content
        # as if it were descriptor text.
        store = _bootstrapped_store()
        result = store.lookup_cpt_descriptor("45380")
        self.assertEqual(result.status, LookupStatus.UNAVAILABLE)
        self.assertNotIn("Column One", result.rationale)


class TestNoValidSourceBehavior(unittest.TestCase):
    def test_lookup_before_any_snapshot_loaded_is_no_valid_source(self):
        store = ReferenceStore()
        result = store.lookup_hcpcs("A0425")
        self.assertEqual(result.status, LookupStatus.NO_VALID_SOURCE)


class TestBuild1And2RegressionSanityWithinBuild3(unittest.TestCase):
    """
    16. lightweight cross-check that Build 3 hasn't altered Build 2's
    authority behavior at all (full regression is the entire existing
    test suite, run separately -- this is a targeted sanity check).
    """

    def test_authority_engine_unchanged_by_build_3_presence(self):
        from billwatch import Source, SourceType
        plan_source = Source(source_type=SourceType.PLAN_POLICY, reference="Plan doc")
        scope = resolve_case_scope(user_selection="private", source_identifier="t")
        decision = evaluate_source_authority(plan_source, scope, ClaimType.COVERAGE_TERMS)
        self.assertEqual(decision.result, AuthorityResult.AUTHORITATIVE)


if __name__ == "__main__":
    unittest.main()
