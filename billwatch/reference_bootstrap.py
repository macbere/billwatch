"""
Demo Bootstrap Reference Data (Build 3).

IMPORTANT -- READ BEFORE USE:

This file is a SMALL, HAND-COMPILED, ILLUSTRATIVE snapshot intended only
for testing and demo purposes. It is explicitly NOT a machine-extracted
bulk import of an official CMS/CDC file.

Why: this build session's sandboxed network egress is restricted to a
fixed allowlist (api.anthropic.com, github.com, pypi.org, npmjs.com, and
similar package/code hosts) that does NOT include cms.gov or cdc.gov --
verified directly in this session (a request to https://www.cms.gov
returned HTTP 403 with header `x-deny-reason: host_not_allowed`). A real
bulk download could not be performed here.

What IS real: the official source citations below (agency, page, and URL)
were independently verified via web search in this session and are
accurate as of the report date. The NCCI PTP relationship between CPT
45378 and 45380 (colonoscopy component bundling) is a long-standing,
widely-documented textbook example in medical billing/coding literature.

What is NOT independently re-verified against a live file this session:
every record below has description_verified / relationship_verified set
to False. Treat every description and relationship here as "plausible,
citation-accurate, but not confirmed against the current live file" --
never as a guaranteed-current fact. See README.md, Reference-data limitation,
for the documented production requirements before replacing this file.
"""

from datetime import date

from .reference_data import HCPCSRecord, ICD10Record, NCCIPairRecord, PlanPolicyRecord, PLAN_POLICY_LICENSE_BASIS


_RETRIEVAL_DATE = date(2026, 8, 9)  # date this bootstrap file was authored

HCPCS_BOOTSTRAP_RECORDS = [
    HCPCSRecord(
        code="A0425",
        description="Ground mileage, per statute mile (ambulance transport)",
        description_verified=False,
        source="CMS HCPCS Level II Quarterly Update (public use file)",
        source_url="https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update",
        effective_date=date(2026, 1, 1),
        version="2026-Q1-illustrative",
        retrieval_date=_RETRIEVAL_DATE,
        license_basis="public_domain_cms",
    ),
    HCPCSRecord(
        code="E0143",
        description="Walker, folding, wheeled, adjustable or fixed height",
        description_verified=False,
        source="CMS HCPCS Level II Quarterly Update (public use file)",
        source_url="https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update",
        effective_date=date(2026, 1, 1),
        version="2026-Q1-illustrative",
        retrieval_date=_RETRIEVAL_DATE,
        license_basis="public_domain_cms",
    ),
]

ICD10CM_BOOTSTRAP_RECORDS = [
    ICD10Record(
        code="Z00.00",
        description="Encounter for general adult medical examination without abnormal findings",
        description_verified=False,
        source="CDC/NCHS ICD-10-CM Files",
        source_url="https://www.cdc.gov/nchs/icd/icd-10-cm/files.html",
        effective_date=date(2025, 10, 1),
        version="FY2026-illustrative",
        retrieval_date=_RETRIEVAL_DATE,
        license_basis="public_domain_nchs",
    ),
    ICD10Record(
        code="K57.30",
        description="Diverticulosis of large intestine without perforation or abscess without bleeding",
        description_verified=False,
        source="CDC/NCHS ICD-10-CM Files",
        source_url="https://www.cdc.gov/nchs/icd/icd-10-cm/files.html",
        effective_date=date(2025, 10, 1),
        version="FY2026-illustrative",
        retrieval_date=_RETRIEVAL_DATE,
        license_basis="public_domain_nchs",
    ),
]

NCCI_PTP_BOOTSTRAP_RECORDS = [
    NCCIPairRecord(
        code_a="45380",  # Column One -- colonoscopy with biopsy
        code_b="45378",  # Column Two -- diagnostic colonoscopy (bundled component)
        relationship="column2_bundled_into_column1",
        modifier_indicator="0",
        relationship_verified=False,
        source="CMS Medicare NCCI Procedure-to-Procedure (PTP) Edits, Practitioner Services",
        source_url="https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-procedure-procedure-ptp-edits",
        effective_date=date(2026, 4, 1),
        version="2026-Q2-illustrative",
        retrieval_date=_RETRIEVAL_DATE,
        license_basis="public_cms_ncci",
    ),
]


PLAN_POLICY_BOOTSTRAP_RECORDS = [
    PlanPolicyRecord(
        plan_id="DEMO-PLAN-001",
        policy_id="DEMO-POL-001",
        rule_type="coverage_rule",
        rule_text=(
            "[DEMO FIXTURE -- SYNTHETIC, AUTHOR-WRITTEN, NOT A REAL INSURER "
            "POLICY, NOT SOURCED FROM ANY ACTUAL PLAN DOCUMENT] This "
            "illustrative plan policy states that an annual wellness "
            "examination (code Z00.00) is covered under this plan without "
            "patient cost-sharing when billed as a standalone preventive "
            "visit."
        ),
        applicable_codes=("Z00.00",),
        patient_cost_share_cents=0,
        source="BillWatch controlled demo fixture (author-written, not sourced from any real insurer)",
        source_url="internal://billwatch/demo-fixtures/plan-policy",
        effective_date=date(2026, 1, 1),
        version="demo-v1",
        retrieval_date=_RETRIEVAL_DATE,
        license_basis=PLAN_POLICY_LICENSE_BASIS,
    ),
]




def load_bootstrap_data(store) -> dict:
    """
    Loads the three bootstrap snapshots into the given ReferenceStore.
    Returns {dataset_name: (snapshot, rejections)} for inspection. Every
    record here is expected to pass validation (this is verified in
    tests/test_reference_data.py); rejections should normally be empty.
    """
    results = {}
    results["hcpcs"] = store.load_snapshot(
        dataset_name="hcpcs",
        records=HCPCS_BOOTSTRAP_RECORDS,
        source="CMS HCPCS Level II Quarterly Update (public use file)",
        source_url="https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update",
        effective_date=date(2026, 1, 1),
        retrieval_date=_RETRIEVAL_DATE,
        version="2026-Q1-illustrative",
        license_basis="public_domain_cms",
    )
    results["icd10cm"] = store.load_snapshot(
        dataset_name="icd10cm",
        records=ICD10CM_BOOTSTRAP_RECORDS,
        source="CDC/NCHS ICD-10-CM Files",
        source_url="https://www.cdc.gov/nchs/icd/icd-10-cm/files.html",
        effective_date=date(2025, 10, 1),
        retrieval_date=_RETRIEVAL_DATE,
        version="FY2026-illustrative",
        license_basis="public_domain_nchs",
    )
    results["ncci_ptp"] = store.load_snapshot(
        dataset_name="ncci_ptp",
        records=NCCI_PTP_BOOTSTRAP_RECORDS,
        source="CMS Medicare NCCI Procedure-to-Procedure (PTP) Edits, Practitioner Services",
        source_url="https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-procedure-procedure-ptp-edits",
        effective_date=date(2026, 4, 1),
        retrieval_date=_RETRIEVAL_DATE,
        version="2026-Q2-illustrative",
        license_basis="public_cms_ncci",
    )
    results["plan_policy"] = store.load_snapshot(
        dataset_name="plan_policy",
        records=PLAN_POLICY_BOOTSTRAP_RECORDS,
        source="BillWatch controlled demo fixture (author-written, not sourced from any real insurer)",
        source_url="internal://billwatch/demo-fixtures/plan-policy",
        effective_date=date(2026, 1, 1),
        retrieval_date=_RETRIEVAL_DATE,
        version="demo-v1",
        license_basis=PLAN_POLICY_LICENSE_BASIS,
    )
    return results
