import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation, Link } from 'react-router-dom'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { authApi, billingApi } from './lib/api'
import { adminAuth } from './lib/adminApi'
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
import { AccountPage } from './pages/AccountPage'
import { Spinner } from './components/ui'
import { AuthCallback } from './pages/AuthCallback'
import { AdminLoginPage } from './pages/admin/AdminLoginPage'
import { AdminDashboardPage } from './pages/admin/AdminDashboardPage'

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

// ── Admin guard ───────────────────────────────────────────────────────────────

function AdminGuard() {
  if (!adminAuth.isLoggedIn()) return <Navigate to="/admin/login" replace />
  return <Outlet />
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
    const shop = p.get('shop') || sessionStorage.getItem('shopiq_shop') || localStorage.getItem('shopiq_shop')
    const host = p.get('host') || sessionStorage.getItem('shopiq_host') || localStorage.getItem('shopiq_host')

    if (shop) {
      const isEmbedded = window.self !== window.top
      if (isEmbedded) {
        // Inside Shopify Admin iframe — full OAuth install
        const apiUrl = import.meta.env.VITE_API_URL || 'https://shopiq-production.up.railway.app'
        let url = `${apiUrl}/auth/shopify/install?shop=${encodeURIComponent(shop)}`
        if (host) url += `&host=${encodeURIComponent(host)}`
        window.location.href = url
        return null
      } else {
        // Standalone / new tab — session expired; redirect merchant back to
        // their Shopify Admin so the app can re-authenticate inside the iframe.
        window.location.href = `https://${shop}/admin`
        return null
      }
    }
    return <Navigate to="/login" replace />
  }

  if (import.meta.env.DEV && !new URLSearchParams(window.location.search).get('shop')) {
    console.warn('[ShopIQ] No ?shop= in URL — App Bridge may not initialize correctly')
  }

  return <Outlet />
}

// ── Dashboard shell ───────────────────────────────────────────────────────────

function GlobalBanners() {
  const { data } = useQuery({
    queryKey: ['billing-usage'],
    queryFn: billingApi.getUsage,
    staleTime: 60_000,
  })

  const sub = data?.subscription
  if (!sub) return null

  const isPastDue = sub.status === 'past_due'
  const isTrialEnding = sub.status === 'trial' && sub.trial_ends_at &&
    Math.ceil((new Date(sub.trial_ends_at).getTime() - Date.now()) / 86400000) <= 3
  const trialDaysLeft = sub.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(sub.trial_ends_at).getTime() - Date.now()) / 86400000))
    : 0
  const hasPendingDowngrade = !!sub.pending_downgrade_plan

  if (!isPastDue && !isTrialEnding && !hasPendingDowngrade) return null

  return (
    <div>
      {isPastDue && (
        <div className="bg-red-500 text-white text-xs font-medium px-6 py-2 flex items-center justify-between">
          <span>Payment failed — your subscription is past due. Features may be restricted soon.</span>
          <Link to="/dashboard/account" className="underline ml-4 flex-shrink-0">Manage billing</Link>
        </div>
      )}
      {isTrialEnding && !isPastDue && (
        <div className="bg-amber-500 text-white text-xs font-medium px-6 py-2 flex items-center justify-between">
          <span>Your trial ends in {trialDaysLeft} day{trialDaysLeft !== 1 ? 's' : ''}.</span>
          <Link to="/dashboard/account" className="underline ml-4 flex-shrink-0">Manage plan</Link>
        </div>
      )}
      {hasPendingDowngrade && !isPastDue && (
        <div className="bg-amber-50 dark:bg-amber-900/30 border-b border-amber-200 dark:border-amber-800 text-xs text-amber-700 dark:text-amber-300 font-medium px-6 py-2 flex items-center justify-between">
          <span>
            Downgrade to {sub.pending_downgrade_plan} scheduled for{' '}
            {sub.pending_downgrade_at
              ? new Date(sub.pending_downgrade_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
              : 'end of billing period'
            }.
          </span>
          <Link to="/dashboard/account" className="underline ml-4 flex-shrink-0">View</Link>
        </div>
      )}
    </div>
  )
}

function DashboardShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-950">
      <Sidebar mobileOpen={sidebarOpen} onMobileClose={() => setSidebarOpen(false)} />
      <main className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 sticky top-0 z-30">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
            aria-label="Open menu"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="6" x2="21" y2="6"/>
              <line x1="3" y1="12" x2="21" y2="12"/>
              <line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>
          <span className="font-semibold text-slate-900 dark:text-slate-100 text-sm">ShopIQ</span>
        </div>
        <GlobalBanners />
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
        {/* ── Admin routes — completely separate auth ───────────────────── */}
        <Route path="/admin/login" element={<AdminLoginPage />} />
        <Route element={<AdminGuard />}>
          <Route path="/admin" element={<AdminDashboardPage />} />
        </Route>

        {/* ✅ Public routes - NO auth required */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/callback" element={<AuthCallback />} />

        {/* ✅ Protected routes - auth required */}
        <Route element={<AuthGuard />}>
          {/* Plans page — full screen, no sidebar */}
          <Route path="/plans" element={<PlansPage />} />

          <Route element={<DashboardShell />}>
            <Route path="/dashboard" element={<AuditPage />} />
            <Route path="/dashboard/account" element={<AccountPage />} />
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