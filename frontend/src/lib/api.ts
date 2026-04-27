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

// App Bridge is loaded as a static blocking <script> in index.html, so
// window.shopify.idToken is always available by the time this module runs.
api.interceptors.request.use(async (config) => {
  try {
    const shopify = (window as any).shopify
    if (typeof shopify?.idToken === 'function') {
      const token = await shopify.idToken()
      if (token) {
        config.headers = config.headers ?? {}
        config.headers.Authorization = `Bearer ${token}`
      }
    }
  } catch (err) {
    console.warn('[ShopIQ] Shopify session token unavailable:', err)
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
  analyze:  () => api.post<{ analysis_id: string; status: string; message: string }>('/returns/analyze'),
  seedDemo: () => api.post<{ analysis_id: string; status: string; message: string }>('/returns/seed-demo'),
  latest:   () => api.get<ReturnAnalysisResults | null>('/returns/latest').then(r => r.data),
  status:   (id: string) => api.get<ReturnAnalysisStatus>(`/returns/${id}/status`).then(r => r.data),
  results:  (id: string) => api.get<ReturnAnalysisResults>(`/returns/${id}/results`).then(r => r.data),
  history:  () => api.get<{ history: ReturnAnalysisResults[] }>('/returns/history').then(r => r.data),
  cancel:   (id: string) => api.post(`/returns/${id}/cancel`),
}

// ── Stock types ───────────────────────────────────────────────────────────────

export interface StockProduct {
  product_id: string
  variant_id: string
  title: string
  variant_title: string | null
  handle: string
  image_url: string | null
  sku: string
  inventory_qty: number
  units_sold_30d: number
  units_sold_prev30d: number
  daily_velocity: number
  velocity_trend: 'rising' | 'falling' | 'stable'
  days_to_stockout: number | null
  price: number
  revenue_at_risk: number
  status: 'urgent' | 'healthy' | 'monitor' | 'dead_stock'
  abc_class: 'A' | 'B' | 'C'
  reorder_qty: number
}

export interface StockAnalysisStatus {
  analysis_id: string
  status: 'queued' | 'running' | 'complete' | 'failed'
  total_skus: number
  error_message: string | null
}

export interface StockAnalysisResults {
  _id: string
  total_skus: number
  skus_urgent: number
  skus_healthy: number
  skus_monitor: number
  skus_dead_stock: number
  total_revenue_at_risk: number
  dead_stock_value: number
  total_inventory_value: number
  capital_efficiency: number
  currency: string
  avg_days_to_stockout: number
  products: StockProduct[]
  insights: string[]
  orders_analyzed: number
  completed_at: string | null
  error_message: string | null
}

// ── Price types ───────────────────────────────────────────────────────────────

export interface CompetitorPrice {
  competitor: string
  url: string
  price: number
  currency: string
  availability: 'in_stock' | 'out_of_stock'
}

export interface PriceProduct {
  product_id: string
  title: string
  handle: string
  image_url: string | null
  our_price: number
  search_query: string
  competitor_prices: CompetitorPrice[]
  min_competitor_price: number | null
  avg_competitor_price: number | null
  price_gap_pct: number | null
  suggested_price: number | null
  status: 'undercut' | 'competitive' | 'overpriced' | 'no_data'
  competitors_count: number
}

export interface PriceAnalysisStatus {
  analysis_id: string
  status: 'queued' | 'running' | 'complete' | 'failed'
  total_products: number
  products_analyzed: number
  error_message: string | null
}

export interface PriceAnalysisResults {
  _id: string
  total_products: number
  products_analyzed: number
  products_undercut: number
  products_competitive: number
  products_overpriced: number
  products_no_data: number
  avg_price_gap_pct: number
  currency: string
  products: PriceProduct[]
  top_competitors: { name: string; count: number }[]
  insights: string[]
  completed_at: string | null
  serpapi_configured: boolean
}

export const priceApi = {
  analyze:  () => api.post<{ analysis_id: string; status: string; message: string }>('/price/analyze'),
  seedDemo: () => api.post<{ analysis_id: string; status: string; message: string }>('/price/seed-demo'),
  config:   () => api.get<{ serpapi_configured: boolean }>('/price/config').then(r => r.data),
  latest:   () => api.get<PriceAnalysisResults | null>('/price/latest').then(r => r.data),
  status:   (id: string) => api.get<PriceAnalysisStatus>(`/price/${id}/status`).then(r => r.data),
  results:  (id: string) => api.get<PriceAnalysisResults>(`/price/${id}/results`).then(r => r.data),
  cancel:   (id: string) => api.post(`/price/${id}/cancel`),
}

export const stockApi = {
  analyze:  () => api.post<{ analysis_id: string; status: string; message: string }>('/stock/analyze'),
  seedDemo: () => api.post<{ analysis_id: string; status: string; message: string }>('/stock/seed-demo'),
  latest:   () => api.get<StockAnalysisResults | null>('/stock/latest').then(r => r.data),
  status:   (id: string) => api.get<StockAnalysisStatus>(`/stock/${id}/status`).then(r => r.data),
  results:  (id: string) => api.get<StockAnalysisResults>(`/stock/${id}/results`).then(r => r.data),
  cancel:   (id: string) => api.post(`/stock/${id}/cancel`),
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