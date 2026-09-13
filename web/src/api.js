import axios from "axios";

const http = axios.create({ baseURL: "/api/v1", timeout: 15000 });

http.interceptors.request.use((config) => {
  const token = localStorage.getItem("gm_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

http.interceptors.response.use(
  (r) => r.data,
  (err) => Promise.reject(new Error(err.response?.data?.detail || err.message))
);

export const api = {
  meta: () => http.get("/meta"),
  rules: () => http.get("/rating-rules"),
  login: (code = `web_${Date.now()}`) => http.post("/auth/login", { code, nickname: "本地体验用户" }),
  me: () => http.get("/me"),
  search: (q) => http.get("/merchants/search", { params: { q } }),
  merchant: (id) => http.get(`/merchants/${id}`),
  evidence: (id, params) => http.get(`/merchants/${id}/evidence`, { params }),
  ratings: (id) => http.get(`/merchants/${id}/ratings/summary`),
  createMerchant: (data) => http.post("/merchants", data),
  rate: (id, data) => http.put(`/ratings/${id}`, data),
  cases: (params) => http.get("/cases", { params }),
  caseDetail: (id) => http.get(`/cases/${id}`),
  rankings: (params) => http.get("/rankings", { params }),
  tip: (data) => http.post("/tips", data),
  myTips: () => http.get("/tips/mine"),
  feedback: (data) => http.post("/feedback", data),
  myFeedback: () => http.get("/feedback/mine/list"),
  shareCard: (id) => http.get(`/share-card/merchant/${id}`),
};

export async function ensureLogin() {
  if (localStorage.getItem("gm_token")) return;
  const res = await api.login();
  localStorage.setItem("gm_token", res.token);
}
