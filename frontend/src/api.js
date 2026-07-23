import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

export async function createDispute({ card_member_id, merchant_id, reason_code, amount }) {
  const { data } = await client.post("/disputes", {
    card_member_id,
    merchant_id,
    reason_code,
    amount,
  });
  return data;
}

export async function submitEvidence(disputeId, { evidence_type, raw_text, submitted_by }) {
  const { data } = await client.post(`/disputes/${disputeId}/evidence`, {
    evidence_type,
    raw_text,
    submitted_by,
  });
  return data;
}

export async function getDisputeStatus(disputeId) {
  const { data } = await client.get(`/disputes/${disputeId}/status`);
  return data;
}

export async function resolveDispute(disputeId) {
  const { data } = await client.post(`/disputes/${disputeId}/resolve`);
  return data;
}

export async function getDecision(disputeId) {
  const { data } = await client.get(`/disputes/${disputeId}/decision`);
  return data;
}

export async function getDashboardMetrics() {
  const { data } = await client.get("/dashboard/metrics");
  return data;
}

export default client;
