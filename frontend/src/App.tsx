import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { authApi } from './lib/api'
import { Sidebar } from './components/layout/Sidebar'
import { AuditPage } from './pages/AuditPage'
import { ReturnsPage } from './pages/ReturnsPage'
import { StockSensePage } from './pages/StockSensePage'
import { PricePulsePage } from './pages/PricePulsePage'
import { LoginPage } from './pages/LoginPage'
import { ComingSoonPage } from './pages/ComingSoonPage'
import { PlansPage } from './pages/PlansPage'
import { Spinner } from './components/ui'
import { AuthCallback } from './pages/AuthCallback'

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
    const shop =
      new URLSearchParams(window.location.search).get('shop') ||
      sessionStorage.getItem('shopiq_shop')
    if (shop) {
      // Embedded context: start OAuth rather than showing login page
      const apiUrl = import.meta.env.VITE_API_URL || 'https://shopiq-production.up.railway.app'
      window.location.href = `${apiUrl}/auth/shopify/install?shop=${encodeURIComponent(shop)}`
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
    <div className="flex min-h-screen bg-slate-50">
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
            <Route path="/dashboard/copy" element={
              <ComingSoonPage module="BulkCopy AI" icon="✦"
                description="Bulk AI product description generator. Upload a CSV of SKUs and get SEO-optimised, brand-voice-matched descriptions pushed straight to Shopify." />
            } />
            <Route path="/dashboard/reviews" element={
              <ComingSoonPage module="ReviewReply Pro" icon="★"
                description="AI-powered review response automation for Google Business, Trustpilot, and Amazon. Approve AI drafts in one click — your brand voice, zero effort." />
            } />
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

            <Route path="/" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}