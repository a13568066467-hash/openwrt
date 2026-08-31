import axios from 'axios';

const api = axios.create({ baseURL: '/api/v1' });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;

export interface Router {
  id: number;
  device_id: string;
  name: string;
  online: boolean;
  last_heartbeat?: string;
}

export interface User {
  id: number;
  username: string;
  quota_remaining_bytes: number;
  upload_rate_kbps: number;
  download_rate_kbps: number;
  status: string;
  quota_expires_at?: string;
}

export interface Plan {
  id: number;
  name: string;
  traffic_mb: number;
  price_cents: number;
  upload_rate_kbps: number;
  download_rate_kbps: number;
  sort_order: number;
  active: boolean;
}

export interface VoucherBatch {
  id: number;
  name: string;
  traffic_mb: number;
  count: number;
  valid_days: number;
  created_at: string;
}

export interface VoucherBatchDetail {
  batch: VoucherBatch;
  codes: string[];
  vouchers: { id: number; status: string; redeemed_by?: number; redeemed_at?: string }[];
}

export interface AuditLog {
  id: number;
  action: string;
  target_type: string;
  target_id: number;
  target_label?: string;
  detail: string;
  created_at: string;
}

export interface UsageRecord {
  id: number;
  session_key: string;
  mac: string;
  delta_bytes: number;
  total_bytes: number;
  recorded_at: string;
}

export interface BrandingConfig {
  site_title: string;
  login_title: string;
  admin_logo: string;
  user_logo: string;
}

export const adminApi = {
  login: (username: string, password: string) =>
    api.post<{ token: string }>('/admin/login', { username, password }),
  getRouters: () => api.get<Router[]>('/admin/routers'),
  getUsers: () => api.get<User[]>('/admin/users'),
  adjustQuota: (id: number, amount_mb: number, note: string) =>
    api.post(`/admin/users/${id}/quota`, { amount_mb, note }),
  updateRate: (id: number, upload_rate_kbps: number, download_rate_kbps: number) =>
    api.put(`/admin/users/${id}/rate`, { upload_rate_kbps, download_rate_kbps }),
  getPlans: () => api.get<Plan[]>('/admin/plans'),
  createPlan: (plan: Partial<Plan>) => api.post<Plan>('/admin/plans', plan),
  updatePlan: (id: number, plan: Partial<Plan>) => api.put(`/admin/plans/${id}`, plan),
  deletePlan: (id: number) => api.delete(`/admin/plans/${id}`),
  getVoucherBatches: () => api.get<VoucherBatch[]>('/admin/vouchers/batches'),
  createVoucherBatch: (name: string, traffic_mb: number, count: number, valid_days: number) =>
    api.post<{ batch_id: number; codes: string[] }>('/admin/vouchers/batch', { name, traffic_mb, count, valid_days }),
  getVoucherBatchDetail: (id: number) => api.get<VoucherBatchDetail>(`/admin/vouchers/batch/${id}`),
  getAuditLogs: () => api.get<AuditLog[]>('/admin/audit-logs'),
  getUsage: () => api.get<UsageRecord[]>('/admin/usage'),
  getBranding: () => api.get<BrandingConfig>('/admin/branding'),
  updateBranding: (config: BrandingConfig) => api.put<BrandingConfig>('/admin/branding', config),
};

export const publicApi = {
  getBranding: () => api.get<BrandingConfig>('/branding'),
};

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function formatTraffic(bytes: number): string {
  const mb = bytes / 1024 / 1024;
  if (mb >= 1024) {
    const gb = mb / 1024;
    return Number.isInteger(gb) ? `${gb} GB` : `${gb.toFixed(1)} GB`;
  }
  return `${mb % 1 === 0 ? mb.toFixed(0) : mb.toFixed(1)} MB`;
}

export function formatTrafficMB(mb: number): string {
  if (mb >= 1024) {
    const gb = mb / 1024;
    return Number.isInteger(gb) ? `${gb} GB` : `${gb.toFixed(1)} GB`;
  }
  return `${mb} MB`;
}

export function formatMB(bytes: number): string {
  return formatTraffic(bytes);
}
