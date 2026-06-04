const BASE_URL = process.env.REACT_APP_API_URL || '';

function getHeaders() {
  const initData = window.Telegram?.WebApp?.initData || '';
  return {
    'Content-Type': 'application/json',
    'X-Telegram-Init-Data': initData,
  };
}

const api = {
  get: (path) => fetch(BASE_URL + path, { headers: getHeaders() }).then(r => r.ok ? r.json() : Promise.reject(r)),
  post: (path, body) => fetch(BASE_URL + path, { method: 'POST', headers: getHeaders(), body: JSON.stringify(body) }).then(r => r.ok ? r.json() : Promise.reject(r)),
  patch: (path, body) => fetch(BASE_URL + path, { method: 'PATCH', headers: getHeaders(), body: JSON.stringify(body) }).then(r => r.ok ? r.json() : Promise.reject(r)),
  delete: (path) => fetch(BASE_URL + path, { method: 'DELETE', headers: getHeaders() }).then(r => r.ok ? r.json() : Promise.reject(r)),
  upload: (path, formData) => fetch(BASE_URL + path, { method: 'POST', headers: { 'X-Telegram-Init-Data': window.Telegram?.WebApp?.initData || '' }, body: formData }).then(r => r.ok ? r.json() : Promise.reject(r)),
};

export const staffApi = {
  me: () => api.get('/api/staff/me'),
  list: () => api.get('/api/staff'),
  get: (id) => api.get(`/api/staff/${id}`),
  create: (data) => api.post('/api/staff', data),
  update: (id, data) => api.patch(`/api/staff/${id}`, data),
};

export const childrenApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return api.get('/api/children' + (q ? '?' + q : ''));
  },
  get: (id) => api.get(`/api/children/${id}`),
  update: (id, data) => api.patch(`/api/children/${id}`, data),
  parents: (id) => api.get(`/api/children/${id}/parents`),
  import: (file, squadId) => {
    const fd = new FormData();
    fd.append('file', file);
    if (squadId) fd.append('squad_id', squadId);
    return api.upload('/api/children/import', fd);
  },
};

export const squadsApi = {
  list: () => api.get('/api/squads'),
};

export const eventsApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return api.get('/api/events' + (q ? '?' + q : ''));
  },
  get: (id) => api.get(`/api/events/${id}`),
  create: (data) => api.post('/api/events', data),
  update: (id, data) => api.patch(`/api/events/${id}`, data),
  delete: (id) => api.delete(`/api/events/${id}`),
  copy: (id, newDate) => api.post(`/api/events/${id}/copy`, { new_date: newDate }),
  members: (id) => api.get(`/api/events/${id}/members`),
};

export const tasksApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return api.get('/api/tasks' + (q ? '?' + q : ''));
  },
  create: (data) => api.post('/api/tasks', data),
  update: (id, data) => api.patch(`/api/tasks/${id}`, data),
  delete: (id) => api.delete(`/api/tasks/${id}`),
};

export const announcementsApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return api.get('/api/announcements' + (q ? '?' + q : ''));
  },
  create: (data) => api.post('/api/announcements', data),
  markRead: (id) => api.post(`/api/announcements/${id}/read`, {}),
};

export const incidentsApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return api.get('/api/incidents' + (q ? '?' + q : ''));
  },
};

export const dutiesApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return api.get('/api/duties' + (q ? '?' + q : ''));
  },
  updateStatus: (id, status) => api.patch(`/api/duties/${id}`, { status }),
};

export const circlesApi = {
  list: () => api.get('/api/circles'),
  members: (id) => api.get(`/api/circles/${id}/members`),
  saveAttendance: (circleId, date, records) => api.post(`/api/circles/${circleId}/attendance`, { date, records }),
};

export default api;
