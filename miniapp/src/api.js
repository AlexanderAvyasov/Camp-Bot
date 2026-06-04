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
  return res.json();
}

export const staffApi = {
  list: () => request("/api/staff"),
  get: (id) => request(`/api/staff/${id}`),
  create: (data) => request("/api/staff", { method: "POST", body: JSON.stringify(data) }),
  update: (id, data) => request(`/api/staff/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
};
