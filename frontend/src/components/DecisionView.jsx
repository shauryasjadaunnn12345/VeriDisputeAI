import { CONFIDENCE_THRESHOLDS, EVIDENCE_TYPE_LABELS } from "../constants";

const OUTCOME_LABELS = {
  refund: "Refund",
  deny: "Deny",
  partial: "Partial Refund",
};

function routingBadge(decision) {
  // human_reviewed here means "flagged as needing human review", not
  // "already reviewed by a human" -- label it accordingly.
  if (decision.human_reviewed) {
    return { label: "Pending Human Review", classes: "bg-amber-100 text-amber-700" };
  }
  if (decision.confidence_score > CONFIDENCE_THRESHOLDS.AUTO_APPROVE_ABOVE) {
    return { label: "Auto-Approved", classes: "bg-green-100 text-green-700" };
  }
  return { label: "Auto-Rejected", classes: "bg-red-100 text-red-700" };
}

function DecisionView({ decision, missingEvidence = [] }) {
  if (!decision) return null;

  const badge = routingBadge(decision);
  const completeness = decision.evidence_completeness_pct ?? 0;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900">Decision</h2>
        <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${badge.classes}`}>
          {badge.label}
        </span>
      </div>

      <div>
        <div className="text-sm text-gray-500 mb-1">Outcome</div>
        <div className="text-2xl font-bold text-gray-900">
          {OUTCOME_LABELS[decision.outcome] || decision.outcome}
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-gray-500">Confidence</span>
          <span className="font-medium text-gray-900">{decision.confidence_score}%</span>
        </div>
        <div className="w-full h-2.5 rounded-full bg-gray-100 overflow-hidden">
          <div
            className="h-full bg-indigo-600 rounded-full transition-all"
            style={{ width: `${Math.min(decision.confidence_score, 100)}%` }}
          />
        </div>
      </div>

      <div>
        <div className="text-sm text-gray-500 mb-1">Evidence Completeness</div>
        <div className="flex items-center gap-3">
          <div className="w-full h-2.5 rounded-full bg-gray-100 overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all"
              style={{ width: `${Math.min(completeness, 100)}%` }}
            />
          </div>
          <span className="text-sm font-medium text-gray-900 whitespace-nowrap">
            {completeness}%
          </span>
        </div>
        {missingEvidence.length > 0 && (
          <p className="text-xs text-gray-500 mt-1.5">
            Missing: {missingEvidence.map((t) => EVIDENCE_TYPE_LABELS[t] || t).join(", ")}
          </p>
        )}
      </div>

      {decision.shap_explanation?.top_features?.length > 0 && (
        <div>
          <div className="text-sm text-gray-500 mb-2">Top Contributing Factors</div>
          <ul className="space-y-1.5">
            {decision.shap_explanation.top_features.map((f, i) => (
              <li
                key={i}
                className="flex items-center justify-between gap-3 text-sm bg-gray-50 rounded-lg px-3 py-2"
              >
                <span className="text-gray-700 font-medium">{f.feature}</span>
                <span className="text-gray-500 text-xs text-right">{f.direction}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {decision.counterfactual_text && (
        <div>
          <div className="text-sm text-gray-500 mb-1">What Would Change the Outcome</div>
          <p className="text-sm text-gray-700 bg-gray-50 rounded-lg px-3 py-2">
            {decision.counterfactual_text}
          </p>
        </div>
      )}

      {decision.reasoning_text && (
        <div>
          <div className="text-sm text-gray-500 mb-1">Reasoning</div>
          <p className="text-sm text-gray-700 bg-gray-50 rounded-lg px-3 py-2">
            {decision.reasoning_text}
          </p>
        </div>
      )}
    </div>
  );
}

export default DecisionView;
