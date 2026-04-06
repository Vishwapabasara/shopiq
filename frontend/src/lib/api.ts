import axios from 'axios'

// In dev, all requests go directly to the backend on port 8000.
// This ensures the session cookie (set on localhost:8000) is always
// sent on the same origin — avoiding the Vite proxy cookie mismatch.
const BASE_URL = (
  import.meta.env.DEV
    ? 'http://localhost:8000'
    : ''
)

export const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AuditIssue {
  rule: string
  category: 'seo' | 'content' | 'ux' | 'catalogue'
  severity: 'critical' | 'warning' | 'info'
  message: string
  fix_hint: string
}

export interface ProductResult {
  shopify_product_id: string
  title: string
  handle: string
  score: number
  issues: AuditIssue[]
  ai_score: number | null
  ai_improvements: string[]
  ai_rewrite: string | null
  ai_verdict: string | null
  image_count: number
  word_count: number
  has_seo_title: boolean
  has_meta_description: boolean
}

export interface CategoryScores {
  seo: number
  content: number
  ux: number
  catalogue: number
}

export interface AuditResults {
  audit_id: string
  overall_score: number
  category_scores: CategoryScores
  products_scanned: number
  critical_count: number
  warning_count: number
  info_count: number
  completed_at: string
  total_filtered: number
  products: ProductResult[]
  pagination: { offset: number; limit: number; total: number; has_more: boolean }
}

export interface AuditStatus {
  audit_id: string
  status: 'queued' | 'running' | 'complete' | 'failed'
  products_scanned: number
  overall_score: number | null
  completed_at: string | null
  error_message: string | null
}

export interface HistoryEntry {
  _id: string
  overall_score: number
  category_scores: CategoryScores
  products_scanned: number
  critical_count: number
  created_at: string
  completed_at: string
}

export interface AuthMe {
  authenticated: boolean
  shop_domain?: string
  shop_name?: string
  plan?: string
  modules_enabled?: string[]
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const authApi = {
  me: () => api.get<AuthMe>('/auth/me').then(r => r.data),
  logout: () => api.post('/auth/logout'),
}

export const auditApi = {
  run: () => api.post<{ audit_id: string; status: string; message: string }>('/audit/run'),
  status: (id: string) => api.get<AuditStatus>(`/audit/${id}/status`).then(r => r.data),
  results: (id: string, params?: { severity?: string; sort?: string; limit?: number; offset?: number }) =>
    api.get<AuditResults>(`/audit/${id}/results`, { params }).then(r => r.data),
  productDetail: (auditId: string, productId: string) =>
    api.get<ProductResult>(`/audit/${auditId}/product/${productId}`).then(r => r.data),
  history: () => api.get<{ history: HistoryEntry[] }>('/audit/history').then(r => r.data),
}