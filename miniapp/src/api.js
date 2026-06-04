const BASE = process.env.REACT_APP_API_URL || "";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const staffApi = {
  list: () => request("/api/staff"),
  get: (id) => request(`/api/staff/${id}`),
  create: (data) => request("/api/staff", { method: "POST", body: JSON.stringify(data) }),
  update: (id, data) => request(`/api/staff/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
};

export const eventsApi = {
  list: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null)).toString();
    return request(`/api/events${qs ? "?" + qs : ""}`);
  },
  create: (data) => request("/api/events", { method: "POST", body: JSON.stringify(data) }),
  update: (id, data) => request(`/api/events/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id) => request(`/api/events/${id}`, { method: "DELETE" }),
  copy: (id, newDate) => request(`/api/events/${id}/copy?new_date=${newDate}`, { method: "POST" }),
  members: (id) => request(`/api/events/${id}/members`),
};
