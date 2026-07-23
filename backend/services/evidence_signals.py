"""
evidence_signals.py

Lightweight keyword/rule-based fallback detectors and validators for
evidence signals that the LLM extraction schema may not capture (or
couldn't, if parsing failed): signature/delivery confirmation, merchant
policy compliance, and tracking-number plausibility.

These are used in the resolve pipeline's feature-vector construction as a
fallback whenever the LLM's explicit extracted field is missing (None) --
if the LLM did return an explicit True/False, that's used directly and
these functions aren't consulted for that piece of evidence.

Negative phrasing is checked first and wins over a bare positive keyword
match, so text like "no signature on file" is correctly read as False
rather than matching on the word "signature" alone.
"""

import re

# Signature confirmation: same co-occurrence philosophy as policy
# compliance below -- a rigid multi-word regex breaks on natural phrasing
# like "the recipient happily signed for it at the front desk" (extra
# words between "recipient" and "signed") or "a signature was required but
# none was ever obtained" (negation phrased without a fixed keyword like
# "not"). Instead: negation markers are checked first over the whole text
# and always win; otherwise any "sign" mention counts as confirmation.
_SIGNATURE_NEGATION_MARKERS = [
    "no signature", "without a signature", "without signature", "not signed",
    "unsigned", "no sig on file", "not obtain", "none was obtained",
    "none obtained", "not provided", "not required", "not available",
    "not on file", "lack of signature", "lacking signature", "didn't sign",
    "did not sign", "wasn't obtained", "was not obtained", "never obtained",
    "no sig ", "no sig.", "no sig,",
]

_COMPLIANCE_NEGATIVE_PATTERNS = [
    r"(?:did not|didn't|failed to)(?:\s+\w+){0,2}\s+(?:comply|follow|meet)",
    r"not in compliance",
    r"policy violation",
    r"violat(?:ed|es|ing)(?:\s+\w+){0,4}\s+polic",
    r"out of compliance",
    r"non[- ]compliant",
]

# Compliance-verb stems and the general topic word ("polic" covers both
# "policy" and "policies"). Rather than a rigid word-distance regex (which
# breaks on natural phrasing like "complied fully with our shipping and
# delivery policy"), a positive match just requires a compliance stem and
# "polic" to both appear in the text, with no negation pattern present --
# negation is checked first, above, and always wins.
_COMPLIANCE_STEMS = [
    r"complie[sd]?\b",
    r"compliant\b",
    r"in compliance",
    r"follow(?:ed|s|ing)?\b",
    r"within polic",
    r"adher(?:ed|es|ence|ing)?\b",
    r"met (?:all )?polic",
    r"conform(?:ed|s|ing)?\b",
]

# Free-text phrases indicating a tracking number is known to be wrong,
# fabricated, or otherwise not to be trusted. Rather than a rigid
# multi-word regex (which breaks on natural phrasing like "the tracking
# number the customer gave us turned out to be wrong"), this is checked
# with sentence-scoped co-occurrence below: a sentence that mentions
# "track" together with any of these discredit words discredits the
# tracking number, without requiring exact word adjacency. Scoping to the
# sentence (rather than the whole evidence text) avoids false positives
# from an unrelated "wrong"/"invalid" elsewhere in the text (e.g. "the
# item itself was wrong, but tracking confirms delivery").
_TRACKING_DISCREDIT_WORDS = [
    "wrong", "incorrect", "invalid", "fake", "bogus", "mismatch",
    "doesn't match", "does not match", "made up", "made-up", "inaccurate",
    "erroneous", "typo", "not valid", "not correct", "not accurate",
]

# Placeholder / non-answer values a tracking_number field can end up
# holding -- these should never count as real evidence. Checked both as an
# exact match and as a substring, since a garbage value might be embedded
# in an otherwise number-shaped string (e.g. "wrongtracking123456").
_INVALID_TRACKING_VALUES = {
    "n/a", "na", "none", "unknown", "test", "testing", "wrong", "invalid",
    "fake", "tbd", "pending", "null", "not available", "no tracking",
    "no tracking number", "no tracking available", "xxxx", "xxxxxxxx",
    "000000", "00000000", "123", "12345", "123456", "wrongnumber",
    "wrong tracking number", "unknown tracking number",
}

_TRACKING_JUNK_SUBSTRINGS = [
    "wrong", "fake", "invalid", "bogus", "unknown", "placeholder", "dummy",
    "sample", "example", "notrack", "n/a", "todo", "tbd", "madeup",
]

_DELIVERY_FAILURE_PATTERNS = [
    r"not (?:yet )?delivered",
    r"undeliver(?:ed|able)",
    r"failed delivery",
    r"delivery (?:failed|exception|attempt failed)",
    r"return(?:ed)? to sender",
    r"lost (?:in transit|package|shipment)",
    r"package (?:lost|missing|damaged)",
    r"still in transit",
    r"in transit\b(?!.*delivered)",
    r"awaiting delivery",
    r"out for delivery\b(?!.*delivered)",
    r"delayed",
    r"exception",
]

_DELIVERY_SUCCESS_PATTERNS = [
    r"successfully delivered",
    r"delivery confirmed",
    r"package (?:was |is )?delivered",
    r"marked delivered",
    r"\bdelivered\b",
]


def _split_sentences(text: str) -> list:
    """Rough sentence splitter -- good enough for co-occurrence scoping,
    doesn't need to be linguistically perfect."""
    return re.split(r"(?<=[.!?])\s+", text)


def _matches_any(patterns, text_lower: str) -> bool:
    return any(re.search(p, text_lower) for p in patterns)


def detect_signature_confirmation(text: str) -> bool:
    """
    Best-effort keyword detection of whether a signature/delivery
    confirmation was on file, from free text. Negation markers (e.g. "no
    signature on file", "none was obtained") are checked first over the
    whole text and always win; otherwise, any mention of "sign" (signed,
    signature, signing, ...) counts as confirmation. Returns False if
    neither is present.
    """
    if not text:
        return False
    text_lower = text.lower()

    if any(marker in text_lower for marker in _SIGNATURE_NEGATION_MARKERS):
        return False
    if "sign" in text_lower:
        return True
    return False


def detect_policy_compliance(text: str) -> bool:
    """
    Best-effort keyword detection of whether merchant-submitted evidence
    indicates the merchant complied with its own return/refund policy.

    Negation patterns (checked first, whole-text) always win, e.g. "policy
    violation" or "did not follow policy". Otherwise, a positive match just
    requires a compliance-verb stem (e.g. "complied", "followed",
    "adhered") AND the word "policy"/"policies" to both appear somewhere in
    the text -- not a rigid word-distance match, since real phrasing like
    "complied fully with our shipping and delivery policy" varies too much
    for that to hold up reliably. Returns False if no clear signal either
    way.
    """
    if not text:
        return False
    text_lower = text.lower()

    if _matches_any(_COMPLIANCE_NEGATIVE_PATTERNS, text_lower):
        return False

    if "polic" not in text_lower:
        return False

    return _matches_any(_COMPLIANCE_STEMS, text_lower)


def is_plausible_tracking_number(tracking_number, context_text: str = "") -> bool:
    """
    Plausibility check for a tracking number string. Rejects None/empty
    values, known placeholder junk ("n/a", "test", "wrong", "123456", ...)
    whether that's the *entire* value or just embedded in it (e.g.
    "wrongtracking123456"), strings that are too short or lack digits to
    be a real carrier tracking number, and low-entropy strings
    (repeated/sequential characters).

    Also checks `context_text` (the full evidence raw_text) for "this
    tracking number is wrong" style language, using sentence-scoped
    co-occurrence (a "track" mention and a discredit word like
    "wrong"/"invalid" in the *same sentence*) rather than a rigid phrase
    match -- so natural phrasing like "the tracking number the customer
    gave us turned out to be wrong" is still caught, while an unrelated
    "wrong"/"invalid" elsewhere in the text (e.g. about the item itself)
    doesn't incorrectly discredit a legitimate tracking number.
    """
    if not tracking_number or not isinstance(tracking_number, str):
        return False

    cleaned = tracking_number.strip()
    if not cleaned:
        return False

    lowered = cleaned.lower()
    if lowered in _INVALID_TRACKING_VALUES:
        return False

    # Junk keyword embedded anywhere in the value itself, e.g. a merchant
    # (or LLM extraction) ending up with something like "wrongtracking123".
    if any(junk in lowered for junk in _TRACKING_JUNK_SUBSTRINGS):
        return False

    # Real carrier tracking numbers are virtually always >= 8 characters.
    if len(cleaned) < 8:
        return False

    # Must contain at least some digits.
    if not any(ch.isdigit() for ch in cleaned):
        return False

    # Reject low-entropy strings (e.g. "00000000", "wrongwrong").
    if len(set(lowered)) <= 2:
        return False

    # The submitter's own text says, somewhere in the same sentence as a
    # "track" mention, that the tracking number is wrong/fake/invalid.
    if context_text:
        for sentence in _split_sentences(context_text.lower()):
            if "track" in sentence and any(word in sentence for word in _TRACKING_DISCREDIT_WORDS):
                return False

    return True


def is_delivery_confirmed(delivery_status) -> bool:
    """
    Returns True only if delivery_status text clearly indicates the
    package was actually delivered. Failure/in-progress language ("in
    transit", "lost", "returned to sender", "not delivered", ...) returns
    False even if the word "delivered" appears nearby. If delivery_status
    is missing/unrecognized, defaults to True so a valid tracking number
    isn't penalized just for lacking a separate status field -- callers
    should combine this with is_plausible_tracking_number.
    """
    if not delivery_status or not isinstance(delivery_status, str):
        return True

    text_lower = delivery_status.lower()

    if _matches_any(_DELIVERY_FAILURE_PATTERNS, text_lower):
        return False
    if _matches_any(_DELIVERY_SUCCESS_PATTERNS, text_lower):
        return True
    return True


if __name__ == "__main__":
    tests = [
        ("Package marked delivered. No signature on file.", detect_signature_confirmation, False),
        ("Recipient signed for the package at the front desk.", detect_signature_confirmation, True),
        ("Delivered with signature confirmation attached.", detect_signature_confirmation, True),
        ("Package left at door, unsigned.", detect_signature_confirmation, False),
        ("The recipient happily signed for it upon arrival, no issues.", detect_signature_confirmation, True),
        ("A signature was required but none was obtained.", detect_signature_confirmation, False),
        ("We complied with our stated return policy in full.", detect_policy_compliance, True),
        ("Merchant failed to follow the refund policy on this order.", detect_policy_compliance, False),
        ("No mention of policy at all here.", detect_policy_compliance, False),
    ]
    for text, fn, expected in tests:
        result = fn(text)
        status = "OK" if result == expected else "MISMATCH"
        print(f"[{status}] {fn.__name__}({text!r}) = {result} (expected {expected})")

    print()
    tracking_tests = [
        ("1Z999AA10123456784", "", True),
        ("wrong", "", False),
        ("123456", "", False),
        ("00000000", "", False),
        (None, "", False),
        ("", "", False),
        ("9405511899223197428490", "", True),
        ("9405511899223197428490", "This tracking number is wrong, does not match our records.", False),
        # Junk embedded directly in the value itself, not just as an exact match.
        ("wrongtracking123456", "", False),
        ("fake1234567890number", "", False),
        # Discredit language with extra words between "tracking" and the
        # discredit word -- previously broke the rigid regex.
        ("1Z999AA10123456784", "The tracking number the customer gave us turned out to be wrong.", False),
        ("1Z999AA10123456784", "Customer says the tracking info provided was completely incorrect.", False),
        # An unrelated "wrong"/"invalid" elsewhere should NOT discredit a
        # legitimate tracking number in a different sentence.
        ("1Z999AA10123456784", "Tracking confirms delivery. The customer's claim is invalid.", True),
        ("1Z999AA10123456784", "Valid tracking, delivered successfully with signature.", True),
    ]
    for tn, ctx, expected in tracking_tests:
        result = is_plausible_tracking_number(tn, ctx)
        status = "OK" if result == expected else "MISMATCH"
        print(f"[{status}] is_plausible_tracking_number({tn!r}, ctx={ctx!r}) = {result} (expected {expected})")

    print()
    delivery_tests = [
        ("delivered", True),
        ("Package marked delivered.", True),
        ("in transit", False),
        ("Package is still in transit to destination.", False),
        ("returned to sender", False),
        ("Delivery failed, package undeliverable.", False),
        (None, True),
    ]
    for ds, expected in delivery_tests:
        result = is_delivery_confirmed(ds)
        status = "OK" if result == expected else "MISMATCH"
        print(f"[{status}] is_delivery_confirmed({ds!r}) = {result} (expected {expected})")
