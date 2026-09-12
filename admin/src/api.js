import axios from "axios";

const http = axios.create({ baseURL: "/admin/v1", timeout: 30000 });

http.interceptors.request.use((c) => {
  const t = localStorage.getItem("gm_admin_token");
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});
http.interceptors.response.use(
  (r) => r.data,
  (e) => {
    if (e.response?.status === 401) {
      localStorage.removeItem("gm_admin_token");
      if (!location.pathname.startsWith("/login")) location.href = "/login";
    }
    const d = e.response?.data?.detail;
    return Promise.reject(new Error(typeof d === "string" ? d : e.message));
  }
);

export const adminApi = {
  login: (username, password) => http.post("/auth/login", { username, password }),
  me: () => http.get("/me"),
  dashboard: () => http.get("/dashboard"),
  sources: (params) => http.get("/sources", { params }),
  clip: (data) => http.post("/sources/clip", data),
  processSource: (id) => http.post(`/sources/${id}/process`),
  assignSource: (id, merchant_id) => http.post(`/sources/${id}/assign`, null, { params: { merchant_id } }),
  importRows: (rows) => http.post("/sources/import", rows),
  evidence: (params) => http.get("/evidence", { params }),
  createEvidence: (data) => http.post("/evidence", data),
  reviewEvidence: (id, data) => http.post(`/evidence/${id}/review`, data),
  merchants: (params) => http.get("/merchants", { params }),
  createMerchant: (data) => http.post("/merchants", data),
  updateMerchant: (id, data) => http.put(`/merchants/${id}`, data),
  merchantAction: (id, action) => http.post(`/merchants/${id}/${action}`),
  merge: (data) => http.post("/merchants/merge", data),
  aliasAction: (mid, aid, action) => http.post(`/merchants/${mid}/aliases/${aid}/${action}`),
  pendingRatings: () => http.get("/ratings/pending"),
  confirmRating: (id, accept) => http.post(`/ratings/${id}/confirm`, { accept }),
  ratingHistory: (id) => http.get(`/ratings/history/${id}`),
  cases: (params) => http.get("/cases", { params }),
  createCase: (data) => http.post("/cases", data),
  updateCase: (id, data) => http.put(`/cases/${id}`, data),
  userRatings: (params) => http.get("/user-ratings", { params }),
  reviewUserRating: (id, data) => http.post(`/user-ratings/${id}/review`, data),
  feedback: (params) => http.get("/feedback", { params }),
  handleFeedback: (id, data) => http.post(`/feedback/${id}/handle`, data),
  tips: (params) => http.get("/tips", { params }),
  handleTip: (id, action) => http.post(`/tips/${id}/${action}`),
  watchlist: () => http.get("/watchlist"),
  createWatch: (data) => http.post("/watchlist", data),
  updateWatch: (id, data) => http.put(`/watchlist/${id}`, data),
  deleteWatch: (id) => http.delete(`/watchlist/${id}`),
  runWatch: (priority) => http.post("/watchlist/run", null, { params: { priority } }),
};
