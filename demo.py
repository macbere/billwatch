"""Command-line entry point for the input-driven BillWatch workflow."""

import argparse
from datetime import date
import json
import os
from pathlib import Path

from billwatch.arbitrary_analysis import (
    AnalysisContext,
    InputDrivenMockProvider,
    analyze_bill,
)
from billwatch.enums import CaseScopeValue
from billwatch.reference_bootstrap import load_bootstrap_data
from billwatch.reference_data import ReferenceStore


def _provider():
    if os.environ.get("GEMINI_API_KEY"):
        from billwatch.genai_sdk_provider import GenAISDKProvider

        return GenAISDKProvider(), "live"
    return InputDrivenMockProvider(), "offline_mock"


def main():
    parser = argparse.ArgumentParser(description="Analyze arbitrary bill text with BillWatch.")
    parser.add_argument(
        "file",
        nargs="?",
        help="optional TXT, CSV, or JSON bill file; otherwise a small sample is used",
    )
    parser.add_argument(
        "--payer-scope",
        choices=("unknown", "medicare", "medicaid", "private_commercial"),
        default="unknown",
    )
    parser.add_argument("--service-date", help="optional service date in YYYY-MM-DD format")
    parser.add_argument(
        "--same-date",
        action="store_true",
        help="confirm that the candidate services share a date of service",
    )
    parser.add_argument(
        "--same-beneficiary",
        action="store_true",
        help="confirm that the candidate services belong to the same beneficiary/claim",
    )
    args = parser.parse_args()

    if args.file:
        bill_text = Path(args.file).read_text(encoding="utf-8")
    else:
        bill_text = (
            "Itemized bill\n"
            "CPT 45378 Diagnostic procedure $400.00\n"
            "CPT 45380 Procedure with biopsy $600.00\n"
            "CPT 99213 Office visit $180.00\n"
        )

    service_date = date.fromisoformat(args.service_date) if args.service_date else None
    context = AnalysisContext(
        payer_scope=CaseScopeValue(args.payer_scope),
        service_date=service_date,
        same_date_confirmed=True if args.same_date else None,
        same_beneficiary_confirmed=True if args.same_beneficiary else None,
    )
    store = ReferenceStore()
    load_bootstrap_data(store)
    provider, mode = _provider()
    result = analyze_bill(bill_text, context, provider, store, gemini_mode=mode)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
