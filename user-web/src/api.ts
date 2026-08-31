import axios from 'axios';

const api = axios.create({ baseURL: '/api/v1' });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('user_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;

export interface User {
  id: number;
  username: string;
  quota_remaining_bytes: number;
  upload_rate_kbps: number;
  download_rate_kbps: number;
  status: string;
}

export interface Plan {
  id: number;
  name: string;
  traffic_mb: number;
  price_cents: number;
  upload_rate_kbps?: number;
  download_rate_kbps?: number;
  sort_order?: number;
}

export interface UserDevice {
  id: number;
  mac: string;
  first_seen: string;
  last_seen: string;
}

export interface UsageRecord {
  id: number;
  delta_bytes: number;
  total_bytes: number;
  recorded_at: string;
}

export interface RedeemedVoucher {
  id: number;
  batch_name: string;
  traffic_mb: number;
  redeemed_at: string | null;
}

export const userApi = {
  login: (username: string, password: string) =>
    api.post<{ token: string; user: User }>('/user/login', { username, password }),
  register: (username: string, password: string) =>
    api.post<{ token: string; user: User }>('/user/register', { username, password }),
  getProfile: () => api.get<User>('/user/profile'),
  getDevices: () => api.get<UserDevice[]>('/user/devices'),
  getUsage: () => api.get<UsageRecord[]>('/user/usage'),
  getRedeemedVouchers: () => api.get<RedeemedVoucher[]>('/user/redeemed-vouchers'),
  redeemVoucher: (code: string) =>
    api.post<{ balance_bytes: number }>('/user/redeem', { code }),
  getPlans: () => api.get<Plan[]>('/user/plans'),
};

export function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function formatMB(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(0)}`;
}

export function formatTrafficMB(mb: number): string {
  if (mb >= 1024) {
    const gb = mb / 1024;
    return Number.isInteger(gb) ? `${gb} GB` : `${gb.toFixed(1)} GB`;
  }
  return `${mb} MB`;
}

export function formatSpeed(kbps: number): string {
  if (!kbps) return '不限速';
  if (kbps >= 1024) return `${(kbps / 1024).toFixed(0)} Mbps`;
  return `${kbps} Kbps`;
}

export function formatRecordTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatRecordDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (d.toDateString() === today.toDateString()) return '今天';
  if (d.toDateString() === yesterday.toDateString()) return '昨天';
  return d.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });
}
