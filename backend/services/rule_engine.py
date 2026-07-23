"""
rule_engine.py

Maps each dispute reason_code to the evidence types required to fully
substantiate it, and scores how complete a given submission is.
"""

REQUIRED_EVIDENCE = {
    "not_received": ["tracking_number", "delivery_confirmation"],
    "not_as_described": ["product_photos", "listing_description"],
    "duplicate_charge": ["transaction_records"],
    "unauthorized": ["account_activity_log"],
}


def evidence_completeness(reason_code: str, submitted_evidence_types: list[str]) -> dict:
    """
    Score how complete a submission's evidence is for a given reason_code.

    Args:
        reason_code: One of the keys in REQUIRED_EVIDENCE.
        submitted_evidence_types: Evidence type strings the user has submitted.

    Returns:
        {
            "completeness_pct": float in [0, 100],
            "missing": list of required evidence type strings not submitted,
        }

    Raises:
        ValueError: if reason_code is not a recognized reason code.
    """

    if reason_code not in REQUIRED_EVIDENCE:
        raise ValueError(
            f"Unknown reason_code '{reason_code}'. "
            f"Expected one of {list(REQUIRED_EVIDENCE.keys())}"
        )

    required = REQUIRED_EVIDENCE[reason_code]
    submitted = set(submitted_evidence_types)

    missing = [item for item in required if item not in submitted]
    n_required = len(required)
    n_present = n_required - len(missing)

    completeness_pct = round((n_present / n_required) * 100, 2) if n_required else 100.0

    return {
        "completeness_pct": completeness_pct,
        "missing": missing,
    }


if __name__ == "__main__":
    test_cases = [
        ("not_received", ["tracking_number"]),
        ("not_as_described", ["product_photos", "listing_description"]),
        ("duplicate_charge", []),
        ("unauthorized", ["account_activity_log", "some_extra_unrelated_evidence"]),
    ]

    for reason_code, submitted in test_cases:
        result = evidence_completeness(reason_code, submitted)
        print(f"reason_code: {reason_code}")
        print(f"  submitted: {submitted}")
        print(f"  completeness_pct: {result['completeness_pct']}%")
        print(f"  missing: {result['missing']}")
        print()
