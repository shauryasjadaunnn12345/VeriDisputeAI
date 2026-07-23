"""
generate_data.py

Generates a synthetic dataset of credit card disputes for training/testing
downstream models. Outcomes are produced by a rule-based function that mixes
several strong heuristics (e.g. missing tracking + no signature -> refund;
high evidence + policy compliance -> deny) with weighted randomness so the
data has realistic overlap and noise rather than perfectly separable classes.

Usage:
    python generate_data.py
"""

import numpy as np
import pandas as pd

# Fix the seed so the dataset is reproducible across runs.
# Remove/change this if you want a different sample each time.
SEED = 42
rng = np.random.default_rng(SEED)

N_ROWS = 1500
REASON_CODES = ["not_received", "not_as_described", "duplicate_charge", "unauthorized"]
OUTCOMES = np.array(["refund", "deny", "partial"])
LABEL_NOISE_FRAC = 0.05


def generate_features(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate the raw feature columns for n dispute cases."""

    reason_code = rng.choice(
        REASON_CODES, size=n, p=[0.30, 0.25, 0.20, 0.25]
    )
    has_tracking = rng.choice([True, False], size=n, p=[0.55, 0.45])
    has_signature_confirmation = rng.choice([True, False], size=n, p=[0.35, 0.65])

    # Response times skew short with a long tail out to 200 hours.
    merchant_response_time_hours = rng.exponential(scale=40, size=n)
    merchant_response_time_hours = np.clip(merchant_response_time_hours, 0, 200)
    merchant_response_time_hours = np.round(merchant_response_time_hours, 1)

    merchant_policy_compliance = rng.choice([True, False], size=n, p=[0.6, 0.4])

    card_member_dispute_history_count = rng.poisson(lam=1.5, size=n)
    card_member_dispute_history_count = np.clip(card_member_dispute_history_count, 0, 10)

    evidence_completeness_pct = rng.normal(loc=60, scale=25, size=n)
    evidence_completeness_pct = np.clip(evidence_completeness_pct, 0, 100)
    evidence_completeness_pct = np.round(evidence_completeness_pct, 1)

    return pd.DataFrame(
        {
            "reason_code": reason_code,
            "has_tracking": has_tracking,
            "has_signature_confirmation": has_signature_confirmation,
            "merchant_response_time_hours": merchant_response_time_hours,
            "merchant_policy_compliance": merchant_policy_compliance,
            "card_member_dispute_history_count": card_member_dispute_history_count,
            "evidence_completeness_pct": evidence_completeness_pct,
        }
    )


def assign_outcomes(df: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    """
    Rule-based outcome assignment.

    Strategy: build up unnormalized weights for [refund, deny, partial] per
    row, then sample from the resulting probability distribution. Five strong
    heuristics (checked in priority order, each claiming only rows not already
    claimed by an earlier one) dominate the weights; everything left over
    falls back to a softer, feature-weighted mix so outcomes still aren't
    perfectly separable.
    """

    n = len(df)
    has_tracking = df["has_tracking"].to_numpy()
    has_signature = df["has_signature_confirmation"].to_numpy()
    policy_compliance = df["merchant_policy_compliance"].to_numpy()
    response_time = df["merchant_response_time_hours"].to_numpy()
    dispute_history = df["card_member_dispute_history_count"].to_numpy()
    evidence_pct = df["evidence_completeness_pct"].to_numpy()
    reason_code = df["reason_code"].to_numpy()

    # Priority-ordered, mutually exclusive "strong rule" masks. Each mask
    # excludes rows already claimed by a higher-priority rule above it.
    strong_refund_mask = (~has_tracking) & (~has_signature)

    strong_deny_mask = (policy_compliance & has_signature) & ~strong_refund_mask

    # Rule 3: very complete evidence + policy compliance is about as close to
    # an open-and-shut case for the merchant as it gets, even without a
    # signature on file -> strongly favors deny.
    high_evidence_deny_mask = (
        (evidence_pct >= 85) & policy_compliance
        & ~strong_refund_mask & ~strong_deny_mask
    )

    # Rule 4: very sparse evidence on its own (regardless of tracking/
    # signature) undermines the merchant's case -> pushes toward
    # refund/partial, away from deny.
    low_evidence_mask = (
        (evidence_pct <= 20)
        & ~strong_refund_mask & ~strong_deny_mask & ~high_evidence_deny_mask
    )

    # Rule 5: a merchant that takes a very long time to respond looks like
    # they're not engaging with the dispute -> pushes away from deny.
    slow_response_mask = (
        (response_time >= 150)
        & ~strong_refund_mask & ~strong_deny_mask
        & ~high_evidence_deny_mask & ~low_evidence_mask
    )

    # Rule 6: partial tracking (delivery shown but no signature) combined
    # with a middling evidence picture is the textbook "split the
    # difference" case -> strongly favors partial refund.
    partial_zone_mask = (
        has_tracking & (~has_signature)
        & (evidence_pct >= 30) & (evidence_pct <= 75)
        & ~strong_refund_mask & ~strong_deny_mask
        & ~high_evidence_deny_mask & ~low_evidence_mask & ~slow_response_mask
    )

    other_mask = ~(
        strong_refund_mask
        | strong_deny_mask
        | high_evidence_deny_mask
        | low_evidence_mask
        | slow_response_mask
        | partial_zone_mask
    )

    refund = np.zeros(n)
    deny = np.zeros(n)
    partial = np.zeros(n)

    # --- Rule 1: missing tracking + no signature -> refund ---
    refund[strong_refund_mask] = 10.0
    deny[strong_refund_mask] = 0.3
    partial[strong_refund_mask] = 1.0

    # --- Rule 2: policy compliance + signature -> deny ---
    refund[strong_deny_mask] = 0.3
    deny[strong_deny_mask] = 10.0
    partial[strong_deny_mask] = 1.0

    # --- Rule 3: high evidence completeness + policy compliance -> deny ---
    refund[high_evidence_deny_mask] = 0.3
    deny[high_evidence_deny_mask] = 10.0
    partial[high_evidence_deny_mask] = 0.6

    # --- Rule 4: low evidence completeness alone -> refund/partial ---
    refund[low_evidence_mask] = 8.0
    deny[low_evidence_mask] = 0.3
    partial[low_evidence_mask] = 2.0

    # --- Rule 5: long merchant response time -> away from deny ---
    refund[slow_response_mask] = 7.5
    deny[slow_response_mask] = 0.3
    partial[slow_response_mask] = 1.8

    # --- Rule 6: partial tracking, no signature, mid-range evidence -> partial ---
    refund[partial_zone_mask] = 1.0
    deny[partial_zone_mask] = 1.0
    partial[partial_zone_mask] = 8.0

    # --- Everything else: weighted randomness from the remaining features ---
    idx = np.where(other_mask)[0]

    refund[idx] = 1.0
    deny[idx] = 1.0
    partial[idx] = 1.0

    # More complete evidence favors the merchant (deny); sparse evidence
    # favors the cardholder (refund). Larger coefficients than before so
    # this bucket isn't left near-uniform random.
    deny[idx] += (evidence_pct[idx] / 100) * 4.0
    refund[idx] += (1 - evidence_pct[idx] / 100) * 3.5

    # A slow merchant response reads as the merchant not engaging, which
    # nudges toward refund and away from deny.
    refund[idx] += np.minimum(response_time[idx] / 200, 1.0) * 2.5
    deny[idx] -= np.minimum(response_time[idx] / 200, 1.0) * 1.0

    # Frequent disputers draw a bit more scrutiny -> slightly more deny/partial.
    deny[idx] += (dispute_history[idx] / 10) * 1.2
    partial[idx] += (dispute_history[idx] / 10) * 0.6

    reason_subset = reason_code[idx]
    refund[idx] += np.where(reason_subset == "unauthorized", 2.0, 0.0)
    refund[idx] += np.where(reason_subset == "duplicate_charge", 1.6, 0.0)
    partial[idx] += np.where(reason_subset == "duplicate_charge", 0.6, 0.0)
    partial[idx] += np.where(reason_subset == "not_as_described", 1.3, 0.0)
    deny[idx] += np.where(reason_subset == "not_as_described", 0.7, 0.0)

    not_received_subset = reason_subset == "not_received"
    deny[idx] += np.where(not_received_subset & has_tracking[idx], 1.3, 0.0)
    refund[idx] += np.where(not_received_subset & ~has_tracking[idx], 1.3, 0.0)

    # Partial tracking without signature confirmation is the classic
    # "partial" gray area.
    partial[idx] += np.where(has_tracking[idx] & ~has_signature[idx], 1.1, 0.0)

    # Keep weights non-negative after the response-time penalty above.
    deny[idx] = np.clip(deny[idx], 0.1, None)

    # Normalize weights into probabilities and sample via inverse-CDF.
    totals = refund + deny + partial
    p_refund = refund / totals
    p_deny = deny / totals
    # p_partial = partial / totals  (implied remainder)

    draw = rng.random(n)
    outcomes = np.where(
        draw < p_refund,
        "refund",
        np.where(draw < p_refund + p_deny, "deny", "partial"),
    )
    return outcomes


def apply_label_noise(outcomes: np.ndarray, frac: float, rng: np.random.Generator) -> np.ndarray:
    """Randomly reassign `frac` of labels to a different outcome to simulate
    mislabeled/ambiguous real-world cases."""

    n = len(outcomes)
    n_noisy = int(round(n * frac))
    noisy_idx = rng.choice(n, size=n_noisy, replace=False)

    noisy_outcomes = outcomes.copy()
    for i in noisy_idx:
        current = noisy_outcomes[i]
        alternatives = OUTCOMES[OUTCOMES != current]
        noisy_outcomes[i] = rng.choice(alternatives)

    return noisy_outcomes


def main():
    df = generate_features(N_ROWS, rng)
    clean_outcomes = assign_outcomes(df, rng)
    df["outcome"] = apply_label_noise(clean_outcomes, LABEL_NOISE_FRAC, rng)

    output_path = "disputes.csv"
    df.to_csv(output_path, index=False)

    print(f"Saved {len(df)} rows to {output_path}\n")
    print("Class balance (outcome):")
    counts = df["outcome"].value_counts()
    pct = df["outcome"].value_counts(normalize=True).round(4) * 100
    balance = pd.DataFrame({"count": counts, "pct": pct.map(lambda x: f"{x:.1f}%")})
    print(balance)


if __name__ == "__main__":
    main()
