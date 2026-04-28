import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { authApi } from './lib/api'
import { Sidebar } from './components/layout/Sidebar'
import { AuditPage } from './pages/AuditPage'
import { ReturnsPage } from './pages/ReturnsPage'
import { StockSensePage } from './pages/StockSensePage'
import { PricePulsePage } from './pages/PricePulsePage'
import { LoginPage } from './pages/LoginPage'
import { ComingSoonPage } from './pages/ComingSoonPage'
import { BulkCopyPage } from './pages/BulkCopyPage'
import { ReviewReplyPage } from './pages/ReviewReplyPage'
import { PlansPage } from './pages/PlansPage'
import { Spinner } from './components/ui'
import { AuthCallback } from './pages/AuthCallback'

// ── Shopify-param-preserving redirect ─────────────────────────────────────────
// React Router's <Navigate> strips query params. This component copies
// shop, host (and other Shopify params if present) into the target URL.

function ShopifyNavigate({ to }: { to: string }) {
  const { search } = useLocation()
  const current = new URLSearchParams(search)
  const qs = new URLSearchParams()

  const shop = current.get('shop') || sessionStorage.getItem('shopiq_shop')
  const host = current.get('host') || sessionStorage.getItem('shopiq_host')
  if (shop) qs.set('shop', shop)
  if (host) qs.set('host', host)
  for (const key of ['hmac', 'timestamp', 'embedded']) {
    const v = current.get(key)
    if (v) qs.set(key, v)
  }

  const q = qs.toString()
  return <Navigate to={q ? `${to}?${q}` : to} replace />
}

// ── Auth guard ────────────────────────────────────────────────────────────────

function AuthGuard() {
  const { data, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: authApi.me,
    retry: false,
    staleTime: 60_000,
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size={32} />
      </div>
    )
  }

  if (!data?.authenticated) {
    const p = new URLSearchParams(window.location.search)
    const shop = p.get('shop') || sessionStorage.getItem('shopiq_shop')
    const host = p.get('host') || sessionStorage.getItem('shopiq_host')
    if (shop) {
      const apiUrl = import.meta.env.VITE_API_URL || 'https://shopiq-production.up.railway.app'
      let url = `${apiUrl}/auth/shopify/install?shop=${encodeURIComponent(shop)}`
      if (host) url += `&host=${encodeURIComponent(host)}`
      window.location.href = url
      return null
    }
    return <Navigate to="/login" replace />
  }

  if (import.meta.env.DEV && !new URLSearchParams(window.location.search).get('shop')) {
    console.warn('[ShopIQ] No ?shop= in URL — App Bridge may not initialize correctly')
  }

  return <Outlet />
}

// ── Dashboard shell ───────────────────────────────────────────────────────────

function DashboardShell() {
  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-950">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0">
        <Outlet />
      </main>
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ✅ Public routes - NO auth required */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/callback" element={<AuthCallback />} />

        {/* ✅ Protected routes - auth required */}
        <Route element={<AuthGuard />}>
          {/* Plans page — full screen, no sidebar */}
          <Route path="/plans" element={<PlansPage />} />

          <Route element={<DashboardShell />}>
            <Route path="/dashboard" element={<AuditPage />} />
            <Route path="/dashboard/stock" element={<StockSensePage />} />
            <Route path="/dashboard/returns" element={<ReturnsPage />} />
            <Route path="/dashboard/price" element={<PricePulsePage />} />
            <Route path="/dashboard/price" element={
              <ComingSoonPage module="PricePulse" icon="◉"
                description="Daily competitor price monitoring across your catalogue. Alerts when you're undercut and suggests optimal price points based on your margin rules." />
            } />
            <Route path="/dashboard/copy" element={<BulkCopyPage />} />
            <Route path="/dashboard/reviews" element={<ReviewReplyPage />} />
            <Route path="/dashboard/leads" element={
              <ComingSoonPage module="LeadForge" icon="◎"
                description="B2B lead enrichment and outreach sequencer. Import a CSV of companies and get enriched contact data with AI-personalised cold emails ready to send." />
            } />
            <Route path="/dashboard/invoice" element={
              <ComingSoonPage module="InvoiceFlow" icon="▤"
                description="Automated invoicing with AI-written payment follow-up sequences. Stripe payment links embedded in every invoice — get paid faster, chase less." />
            } />
            <Route path="/dashboard/contract" element={
              <ComingSoonPage module="ContractPilot" icon="◻"
                description="AI contract risk analyser. Upload any PDF contract and get a plain-English breakdown of payment terms, IP clauses, red flags, and negotiation points." />
            } />
            <Route path="/dashboard/onboard" element={
              <ComingSoonPage module="OnboardKit" icon="▷"
                description="Branded client onboarding portals. Build drag-and-drop intake flows with file uploads, automated reminders, and kickoff scheduling — no more chasing clients." />
            } />

            <Route path="/" element={<ShopifyNavigate to="/dashboard" />} />
          </Route>
        </Route>

        <Route path="*" element={<ShopifyNavigate to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  )
}