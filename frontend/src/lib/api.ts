import axios from 'axios'

// In dev, all requests go directly to the backend on port 8000.
// This ensures the session cookie (set on localhost:8000) is always
// sent on the same origin — avoiding the Vite proxy cookie mismatch.
const BASE_URL = (
  import.meta.env.DEV
    ? 'http://localhost:8000'
    : import.meta.env.VITE_API_URL || ''
)

export const api = axios.create({
  baseURL: import.meta.env.DEV ? 'http://localhost:8000' : import.meta.env.VITE_API_URL || '',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

// Attach Shopify session token when running inside Shopify Admin (embedded app)
api.interceptors.request.use(async (config) => {
  try {
    const shopify = (window as any).shopify
    if (shopify?.idToken) {
      // 3 s timeout — if App Bridge hasn't initialized, fall through to cookie auth
      const token = await Promise.race([
        shopify.idToken() as Promise<string>,
        new Promise<never>((_, reject) => setTimeout(() => reject(new Error('timeout')), 3000)),
      ])
      config.headers = config.headers ?? {}
      config.headers['Authorization'] = `Bearer ${token}`
    }
  } catch {
    // Not in embedded context or App Bridge not ready — cookie auth is the fallback
  }
  return config
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
  // Per-product score breakdown (0–50 each)
  content_score?: number
  visual_score?: number
  title_score?: number
  // First product image thumbnail
  image_url?: string | null
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
  product_results: ProductResult[]
  total_products: number
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
  scope_issue?: boolean
  missing_scopes?: string[]
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const authApi = {
  me: () => api.get<AuthMe>('/auth/me').then(r => r.data),
  logout: () => api.post('/auth/logout'),
}

// ── Returns types ─────────────────────────────────────────────────────────────

export interface ReturnAnalysisStatus {
  analysis_id: string
  status: 'queued' | 'running' | 'complete' | 'failed'
  orders_analyzed: number
  error_message: string | null
}

export interface ReturnProduct {
  product_id: string
  title: string
  handle: string
  image_url: string | null
  total_orders: number
  total_returns: number
  return_rate: number
  refund_value: number
  top_reason: string
}

export interface FlaggedCustomer {
  customer_id: string
  name: string
  email: string
  total_orders: number
  total_returns: number
  return_rate: number
  risk_level: 'high' | 'medium' | 'low'
}

export interface MonthlyTrend {
  month: string
  orders: number
  returns: number
  return_rate: number
  refund_value: number
}

export interface ReturnAnalysisResults {
  _id: string
  orders_analyzed: number
  total_refunded: number
  return_rate: number
  total_refund_value: number
  currency: string
  reason_breakdown: Record<string, number>
  top_returned_products: ReturnProduct[]
  flagged_customers: FlaggedCustomer[]
  monthly_trend: MonthlyTrend[]
  insights: string[]
  completed_at: string
}

export const returnsApi = {
  analyze: () => api.post<{ analysis_id: string; status: string; message: string }>('/returns/analyze'),
  latest:  () => api.get<ReturnAnalysisResults | null>('/returns/latest').then(r => r.data),
  status:  (id: string) => api.get<ReturnAnalysisStatus>(`/returns/${id}/status`).then(r => r.data),
  results: (id: string) => api.get<ReturnAnalysisResults>(`/returns/${id}/results`).then(r => r.data),
  history: () => api.get<{ history: ReturnAnalysisResults[] }>('/returns/history').then(r => r.data),
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