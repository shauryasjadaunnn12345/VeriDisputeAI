import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getDashboardMetrics } from "../api";

const OUTCOME_COLORS = { refund: "#6366f1", deny: "#ef4444", partial: "#f59e0b" };

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="text-sm text-gray-500 mb-1">{label}</div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  );
}

function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await getDashboardMetrics();
        if (!cancelled) setMetrics(data);
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || "Could not load dashboard metrics.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <p className="text-sm text-gray-500">Loading dashboard...</p>;
  }
  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }
  if (!metrics || metrics.total_decisions === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <p className="text-sm text-gray-500">
          No resolved disputes yet. Resolve a dispute to see metrics here.
        </p>
      </div>
    );
  }

  const outcomeData = Object.entries(metrics.outcome_rates).map(([outcome, rate]) => ({
    outcome,
    rate,
  }));
  const confidenceData = Object.entries(metrics.confidence_distribution).map(
    ([bucket, count]) => ({ bucket, count })
  );

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Total Decisions" value={metrics.total_decisions} />
        <StatCard
          label="Avg Resolution Time"
          value={
            metrics.avg_resolution_time_seconds != null
              ? `${metrics.avg_resolution_time_seconds}s`
              : "—"
          }
        />
        <StatCard label="% Human Reviewed" value={`${metrics.pct_human_reviewed}%`} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Outcome Rates</h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={outcomeData}
                dataKey="rate"
                nameKey="outcome"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label={({ outcome, rate }) => `${outcome}: ${rate}%`}
              >
                {outcomeData.map((entry) => (
                  <Cell key={entry.outcome} fill={OUTCOME_COLORS[entry.outcome] || "#94a3b8"} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">
            Confidence Score Distribution
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={confidenceData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
