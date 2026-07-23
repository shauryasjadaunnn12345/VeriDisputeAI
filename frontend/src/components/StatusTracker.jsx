import { useEffect, useState } from "react";
import { getDisputeStatus } from "../api";

const POLL_INTERVAL_MS = 4000;

const STATUS_LABELS = {
  open: "Open",
  resolved: "Resolved",
  pending_review: "Pending Human Review",
};

const STATUS_STYLES = {
  open: "bg-gray-100 text-gray-700",
  resolved: "bg-green-100 text-green-700",
  pending_review: "bg-amber-100 text-amber-700",
};

function StatusTracker({ disputeId, refreshKey }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!disputeId) return;

    let cancelled = false;

    const poll = async () => {
      try {
        const data = await getDisputeStatus(disputeId);
        if (!cancelled) {
          setStatus(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || "Could not fetch status.");
        }
      }
    };

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [disputeId, refreshKey]);

  if (!disputeId) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h2 className="text-base font-semibold text-gray-900 mb-3">Dispute Status</h2>
      {error && <p className="text-sm text-red-600 mb-2">{error}</p>}
      {status ? (
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">Dispute #{status.dispute_id}</span>
          <div className="flex items-center gap-4">
            <span className="text-gray-600">
              Evidence submitted: <strong>{status.evidence_count}</strong>
            </span>
            <span
              className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                STATUS_STYLES[status.status] || "bg-gray-100 text-gray-700"
              }`}
            >
              {STATUS_LABELS[status.status] || status.status}
            </span>
          </div>
        </div>
      ) : (
        <p className="text-sm text-gray-500">Loading status...</p>
      )}
    </div>
  );
}

export default StatusTracker;
