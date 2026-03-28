const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001";

export async function chat(payload) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Chat request failed");
  return res.json();
}

export async function submitHitlDecision({ actionId, decision, selectedStartIso }) {
  const res = await fetch(`${API_BASE}/hitl/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action_id: actionId,
      decision,
      selected_start_iso: selectedStartIso ?? null,
    }),
  });
  if (!res.ok) throw new Error("HITL submission failed");
  return res.json();
}

export async function getPreferences(userId) {
  const res = await fetch(`${API_BASE}/preferences/${userId}`);
  if (!res.ok) throw new Error("Failed to load preferences");
  return res.json();
}

export async function putPreferences(userId, prefs) {
  const res = await fetch(`${API_BASE}/preferences/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prefs),
  });
  if (!res.ok) throw new Error("Failed to save preferences");
  return res.json();
}

export async function getEvents(userId, startIso, endIso) {
  const url = new URL(`${API_BASE}/events`);
  url.searchParams.append("user_id", userId);
  url.searchParams.append("start_iso", startIso);
  url.searchParams.append("end_iso", endIso);
  
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error("Failed to load events");
  return res.json();
}
