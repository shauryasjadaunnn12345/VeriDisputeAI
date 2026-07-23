export const REASON_CODES = [
  { value: "not_received", label: "Not Received" },
  { value: "not_as_described", label: "Not as Described" },
  { value: "duplicate_charge", label: "Duplicate Charge" },
  { value: "unauthorized", label: "Unauthorized" },
];

// Mirrors backend/services/rule_engine.py's REQUIRED_EVIDENCE. Duplicated
// here (rather than fetched) since there's no endpoint exposing it; keep
// this in sync if the backend rule engine changes.
export const REQUIRED_EVIDENCE = {
  not_received: ["tracking_number", "delivery_confirmation"],
  not_as_described: ["product_photos", "listing_description"],
  duplicate_charge: ["transaction_records"],
  unauthorized: ["account_activity_log"],
};

export const ALL_EVIDENCE_TYPES = [
  "tracking_number",
  "delivery_confirmation",
  "product_photos",
  "listing_description",
  "transaction_records",
  "account_activity_log",
];

export const EVIDENCE_TYPE_LABELS = {
  tracking_number: "Tracking Number",
  delivery_confirmation: "Delivery Confirmation",
  product_photos: "Product Photos",
  listing_description: "Listing Description",
  transaction_records: "Transaction Records",
  account_activity_log: "Account Activity Log",
};

// Mirrors the routing thresholds in backend/routers/disputes.py.
export const CONFIDENCE_THRESHOLDS = {
  AUTO_REJECT_BELOW: 20,
  AUTO_APPROVE_ABOVE: 85,
};

// The backend doesn't expose an endpoint listing evidence submitted so far
// for a dispute, so we track submitted types client-side during the active
// session and compute what's still missing using the same REQUIRED_EVIDENCE
// mapping the rule engine uses. (evidence_completeness_pct itself always
// comes from the backend -- this is just for the "missing" list display.)
export function getMissingEvidence(reasonCode, submittedTypes) {
  const required = REQUIRED_EVIDENCE[reasonCode] || [];
  const submittedSet = new Set(submittedTypes);
  return required.filter((type) => !submittedSet.has(type));
}
