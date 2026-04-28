import axios from 'axios'

const TOKEN_KEY = 'shopiq_admin_token'

export const adminHttp = axios.create({
  baseURL: import.meta.env.DEV ? 'http://localhost:8000' : import.meta.env.VITE_API_URL || '',
})

adminHttp.interceptors.request.use(config => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers['X-Admin-Token'] = token
  return config
})

export const adminAuth = {
  login: (username: string, password: string) =>
    adminHttp.post<{ token: string; expires_in: number }>('/admin/login', { username, password }).then(r => r.data),
  logout: () => localStorage.removeItem(TOKEN_KEY),
  isLoggedIn: () => !!localStorage.getItem(TOKEN_KEY),
  saveToken: (token: string) => localStorage.setItem(TOKEN_KEY, token),
}

export interface AdminStats {
  total_stores: number
  stores_by_plan: { free: number; pro: number; enterprise: number }
  mrr: number
  active_trials: number
  past_due: number
  new_this_month: number
  total_audits_this_month: number
  total_copy_this_month: number
}

export interface AdminTenant {
  id: string
  shop_domain: string
  shop_name: string
  plan: string
  subscription_status: string
  trial_ends_at: string | null
  installed_at: string | null
  activated_on: string | null
  pending_downgrade_plan: string | null
  shopify_charge_id: string | null
  usage: {
    audits_used: number
    audits_limit: number
    copy_used: number
    copy_limit: number
    last_updated: string | null
  }
}

export interface AdminEvent {
  id: string
  tenant_id: string
  shop_domain: string
  event_type: string
  from_plan: string | null
  to_plan: string
  amount: number
  created_at: string | null
}

export interface PagedResponse<T> {
  data: T[]
  total: number
  page: number
  pages: number
}

export const adminApi = {
  stats: () =>
    adminHttp.get<AdminStats>('/admin/stats').then(r => r.data),

  tenants: (params: { search?: string; plan?: string; status?: string; page?: number }) =>
    adminHttp.get<{ tenants: AdminTenant[]; total: number; page: number; pages: number }>(
      '/admin/tenants', { params }
    ).then(r => r.data),

  overridePlan: (tenantId: string, plan: string) =>
    adminHttp.patch(`/admin/tenants/${tenantId}/plan`, { plan }).then(r => r.data),

  events: (params: { page?: number }) =>
    adminHttp.get<{ events: AdminEvent[]; total: number; page: number; pages: number }>(
      '/admin/events', { params }
    ).then(r => r.data),
}
