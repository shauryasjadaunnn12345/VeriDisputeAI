import { useState } from "react";
import RoleToggle from "./components/RoleToggle";
import DisputeForm from "./components/DisputeForm";
import EvidenceForm from "./components/EvidenceForm";
import StatusTracker from "./components/StatusTracker";
import DecisionView from "./components/DecisionView";
import Dashboard from "./components/Dashboard";
import { resolveDispute } from "./api";
import { getMissingEvidence } from "./constants";

function NavTabs({ view, onChange }) {
  const tabs = [
    { value: "dispute", label: "Disputes" },
    { value: "dashboard", label: "Dashboard" },
  ];
  return (
    <nav className="inline-flex rounded-lg border border-gray-300 bg-gray-100 p-0.5">
      {tabs.map((t) => (
        <button
          key={t.value}
          type="button"
          onClick={() => onChange(t.value)}
          className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
            view === t.value
              ? "bg-white shadow text-indigo-700"
              : "text-gray-600 hover:text-gray-900"
          }`}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}

function App() {
  const [role, setRole] = useState("card_member");
  const [view, setView] = useState("dispute"); // "dispute" | "dashboard"

  // Card member flow state.
  const [activeDispute, setActiveDispute] = useState(null);
  const [submittedTypes, setSubmittedTypes] = useState([]);
  const [decision, setDecision] = useState(null);
  const [resolving, setResolving] = useState(false);
  const [resolveError, setResolveError] = useState(null);
  const [statusRefreshKey, setStatusRefreshKey] = useState(0);

  // Merchant flow state -- merchants have no auth/lookup here, so they
  // target a dispute by ID (given to them by the card member out-of-band).
  const [merchantDisputeIdInput, setMerchantDisputeIdInput] = useState("");
  const merchantDisputeId = merchantDisputeIdInput ? Number(merchantDisputeIdInput) : null;

  const handleDisputeCreated = (dispute) => {
    setActiveDispute(dispute);
    setSubmittedTypes([]);
    setDecision(null);
    setResolveError(null);
  };

  const handleEvidenceSubmitted = (evidence) => {
    setSubmittedTypes((prev) => [...prev, evidence.evidence_type]);
    setStatusRefreshKey((k) => k + 1);
  };

  const handleResolve = async () => {
    if (!activeDispute) return;
    setResolving(true);
    setResolveError(null);
    try {
      const result = await resolveDispute(activeDispute.id);
      setDecision(result);
      setStatusRefreshKey((k) => k + 1);
    } catch (err) {
      setResolveError(err.response?.data?.detail || "Failed to resolve dispute.");
    } finally {
      setResolving(false);
    }
  };

  const handleNewDispute = () => {
    setActiveDispute(null);
    setSubmittedTypes([]);
    setDecision(null);
    setResolveError(null);
  };

  const missingEvidence = activeDispute
    ? getMissingEvidence(activeDispute.reason_code, submittedTypes)
    : [];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-lg font-bold text-gray-900">Dispute Resolution</h1>
          <div className="flex items-center gap-3">
            <NavTabs view={view} onChange={setView} />
            {view === "dispute" && <RoleToggle role={role} onChange={setRole} />}
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {view === "dashboard" ? (
          <Dashboard />
        ) : role === "card_member" ? (
          <div className="space-y-6">
            {!activeDispute ? (
              <DisputeForm onCreated={handleDisputeCreated} />
            ) : (
              <>
                <div className="flex items-center justify-between bg-indigo-50 border border-indigo-100 rounded-xl px-4 py-3">
                  <div className="text-sm text-indigo-900">
                    Active dispute: <strong>#{activeDispute.id}</strong> ({activeDispute.reason_code})
                  </div>
                  <button
                    type="button"
                    onClick={handleNewDispute}
                    className="text-sm font-medium text-indigo-700 hover:text-indigo-900"
                  >
                    Start new dispute
                  </button>
                </div>

                <StatusTracker disputeId={activeDispute.id} refreshKey={statusRefreshKey} />

                <EvidenceForm
                  disputeId={activeDispute.id}
                  submittedBy="card_member"
                  onSubmitted={handleEvidenceSubmitted}
                />

                <div className="bg-white rounded-xl border border-gray-200 p-5">
                  <button
                    type="button"
                    onClick={handleResolve}
                    disabled={resolving}
                    className="w-full bg-gray-900 text-white text-sm font-medium rounded-lg px-4 py-2.5 hover:bg-gray-800 disabled:opacity-50 transition-colors"
                  >
                    {resolving ? "Resolving..." : "Resolve Dispute"}
                  </button>
                  {resolveError && <p className="text-sm text-red-600 mt-2">{resolveError}</p>}
                </div>

                {decision && (
                  <DecisionView decision={decision} missingEvidence={missingEvidence} />
                )}
              </>
            )}
          </div>
        ) : (
          <div className="space-y-6">
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Dispute ID
              </label>
              <input
                type="number"
                value={merchantDisputeIdInput}
                onChange={(e) => setMerchantDisputeIdInput(e.target.value)}
                placeholder="Enter the dispute ID provided by the card member"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {merchantDisputeId != null && !Number.isNaN(merchantDisputeId) && (
              <>
                <StatusTracker disputeId={merchantDisputeId} />
                <EvidenceForm
                  disputeId={merchantDisputeId}
                  submittedBy="merchant"
                  onSubmitted={() => {}}
                />
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;

