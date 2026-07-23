import { useState } from "react";
import { createDispute } from "../api";
import { REASON_CODES } from "../constants";

function DisputeForm({ onCreated }) {
  const [form, setForm] = useState({
    card_member_id: "",
    merchant_id: "",
    reason_code: REASON_CODES[0].value,
    amount: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const dispute = await createDispute({
        card_member_id: form.card_member_id,
        merchant_id: form.merchant_id,
        reason_code: form.reason_code,
        amount: parseFloat(form.amount),
      });
      onCreated(dispute);
      setForm((f) => ({ ...f, amount: "" }));
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create dispute.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h2 className="text-base font-semibold text-gray-900 mb-4">File a New Dispute</h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Card Member ID
          </label>
          <input
            name="card_member_id"
            value={form.card_member_id}
            onChange={handleChange}
            required
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            placeholder="cm_123"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Merchant ID
          </label>
          <input
            name="merchant_id"
            value={form.merchant_id}
            onChange={handleChange}
            required
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            placeholder="merch_456"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
          <select
            name="reason_code"
            value={form.reason_code}
            onChange={handleChange}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {REASON_CODES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Amount ($)</label>
          <input
            name="amount"
            type="number"
            step="0.01"
            min="0"
            value={form.amount}
            onChange={handleChange}
            required
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            placeholder="89.99"
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-indigo-600 text-white text-sm font-medium rounded-lg px-4 py-2 hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "Creating..." : "Create Dispute"}
        </button>
      </form>
    </div>
  );
}

export default DisputeForm;
