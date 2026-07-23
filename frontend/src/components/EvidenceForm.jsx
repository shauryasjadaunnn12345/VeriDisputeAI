import { useState } from "react";
import { submitEvidence } from "../api";
import { ALL_EVIDENCE_TYPES, EVIDENCE_TYPE_LABELS } from "../constants";

function EvidenceForm({ disputeId, submittedBy, onSubmitted }) {
  const [form, setForm] = useState({
    evidence_type: ALL_EVIDENCE_TYPES[0],
    raw_text: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
    setSuccess(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const evidence = await submitEvidence(disputeId, {
        evidence_type: form.evidence_type,
        raw_text: form.raw_text,
        submitted_by: submittedBy,
      });
      onSubmitted?.(evidence);
      setForm((f) => ({ ...f, raw_text: "" }));
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to submit evidence.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h2 className="text-base font-semibold text-gray-900 mb-4">
        Submit Evidence <span className="text-gray-400 font-normal">(as {submittedBy === "merchant" ? "merchant" : "card member"})</span>
      </h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Evidence Type
          </label>
          <select
            name="evidence_type"
            value={form.evidence_type}
            onChange={handleChange}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {ALL_EVIDENCE_TYPES.map((type) => (
              <option key={type} value={type}>
                {EVIDENCE_TYPE_LABELS[type] || type}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Details
          </label>
          <textarea
            name="raw_text"
            value={form.raw_text}
            onChange={handleChange}
            required
            rows={4}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            placeholder="Describe the evidence, e.g. tracking number, delivery status, dates, amounts..."
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        {success && <p className="text-sm text-green-600">Evidence submitted.</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-indigo-600 text-white text-sm font-medium rounded-lg px-4 py-2 hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "Submitting..." : "Submit Evidence"}
        </button>
      </form>
    </div>
  );
}

export default EvidenceForm;
