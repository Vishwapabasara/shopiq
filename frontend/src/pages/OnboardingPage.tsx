import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { stockApi } from '../lib/api'
import logo from '../assets/shopiq-lettermark-1200.png'
import { ShareCard } from '../components/stock/ShareCard'

type Phase = 'checking' | 'scanning' | 'result' | 'error'

const SCAN_STEPS = [
  'Connecting to your Shopify store…',
  'Fetching your product catalog…',
  'Pulling 60 days of order history…',
  'Analysing sales velocity per SKU…',
  'Calculating dead stock capital…',
  'Building your inventory report…',
]

function fmt(n: number, currency: string) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(n)
}

export function OnboardingPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [phase, setPhase] = useState<Phase>('checking')
  const [stepIdx, setStepIdx] = useState(0)
  const [result, setResult] = useState<{
    dead_stock_value: number
    skus_dead_stock: number
    total_inventory_value: number
    skus_urgent: number
    currency: string
    shop_domain?: string
  } | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const stepRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const analysisId = useRef<string | null>(null)

  const shop = searchParams.get('shop')
  const host = searchParams.get('host')

  const goToDashboard = () => {
    localStorage.setItem('shopiq_onboarded', '1')
    const params = new URLSearchParams()
    if (shop) params.set('shop', shop)
    if (host) params.set('host', host)
    const qs = params.toString()
    navigate(`/dashboard/stock${qs ? `?${qs}` : ''}`, { replace: true })
  }

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    if (stepRef.current) { clearInterval(stepRef.current); stepRef.current = null }
  }

  const startScan = async () => {
    setPhase('scanning')
    setStepIdx(0)

    // cycle through step labels for UX
    stepRef.current = setInterval(() => {
      setStepIdx(i => Math.min(i + 1, SCAN_STEPS.length - 1))
    }, 2800)

    try {
      const res = await stockApi.analyze()
      const id = res.data.analysis_id
      analysisId.current = id
      localStorage.setItem('shopiq_active_stock', id)

      pollRef.current = setInterval(async () => {
        try {
          const status = await stockApi.status(id)
          if (status.status === 'complete') {
            stopPolling()
            const data = await stockApi.results(id)
            setResult({
              dead_stock_value:      data.dead_stock_value,
              skus_dead_stock:       data.skus_dead_stock,
              total_inventory_value: data.total_inventory_value,
              skus_urgent:           data.skus_urgent,
              currency:              data.currency || 'USD',
              shop_domain:           shop ?? undefined,
            })
            setPhase('result')
          } else if (status.status === 'failed') {
            stopPolling()
            setErrorMsg(status.error_message ?? 'Analysis failed.')
            setPhase('error')
          }
        } catch {
          stopPolling()
          setErrorMsg('Lost connection while scanning. Please try again.')
          setPhase('error')
        }
      }, 2000)
    } catch (err: any) {
      stopPolling()
      const msg = err?.response?.data?.detail ?? 'Could not start analysis.'
      setErrorMsg(msg)
      setPhase('error')
    }
  }

  useEffect(() => {
    let cancelled = false

    const init = async () => {
      try {
        // Check if this store already has a completed scan
        const latest = await stockApi.latest()
        if (cancelled) return

        if (latest && (latest as any).dead_stock_value !== undefined) {
          // Returning user — skip onboarding, go straight to their results
          goToDashboard()
          return
        }
      } catch {
        // No prior scan or API error — proceed with onboarding
      }

      if (!cancelled) startScan()
    }

    init()
    return () => {
      cancelled = true
      stopPolling()
    }
  }, [])

  // ── Checking phase ──────────────────────────────────────────────────────────
  if (phase === 'checking') {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <img src={logo} alt="ShopIQ" className="w-12 h-12 object-contain" />
          <div className="flex gap-1.5">
            {[0, 1, 2].map(i => (
              <div
                key={i}
                className="w-2 h-2 bg-brand-600 rounded-full animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </div>
        </div>
      </div>
    )
  }

  // ── Scanning phase ──────────────────────────────────────────────────────────
  if (phase === 'scanning') {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center p-6">
        <div className="w-full max-w-md text-center">
          <img src={logo} alt="ShopIQ" className="w-14 h-14 object-contain mx-auto mb-8" />
          <h1 className="text-2xl font-bold text-zinc-900 mb-2">Scanning your store</h1>
          <p className="text-zinc-500 text-sm mb-10">
            We're analysing your inventory to find exactly how much cash is tied up in slow-moving products.
          </p>

          {/* Animated ring */}
          <div className="relative w-28 h-28 mx-auto mb-10">
            <svg className="w-28 h-28 -rotate-90" viewBox="0 0 112 112">
              <circle cx="56" cy="56" r="48" fill="none" stroke="#e2e8f0" strokeWidth="8"/>
              <circle
                cx="56" cy="56" r="48"
                fill="none"
                stroke="#4f46e5"
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray="301.6"
                strokeDashoffset="75"
                className="transition-all duration-700"
                style={{
                  strokeDashoffset: 301.6 - (301.6 * Math.min((stepIdx + 1) / SCAN_STEPS.length, 0.92)),
                }}
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-lg font-bold text-brand-600">
                {Math.round(Math.min(((stepIdx + 1) / SCAN_STEPS.length) * 92, 92))}%
              </span>
            </div>
          </div>

          {/* Step list */}
          <div className="space-y-2 text-left max-w-xs mx-auto">
            {SCAN_STEPS.map((step, i) => {
              const done = i < stepIdx
              const active = i === stepIdx
              return (
                <div key={step} className="flex items-center gap-3">
                  <div className={`w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center text-[10px] font-bold
                    ${done ? 'bg-emerald-500 text-white' : active ? 'bg-brand-600 text-white' : 'bg-zinc-100 text-zinc-300'}`}>
                    {done ? '✓' : i + 1}
                  </div>
                  <span className={`text-xs ${done ? 'text-emerald-600' : active ? 'text-zinc-800 font-medium' : 'text-zinc-300'}`}>
                    {step}
                  </span>
                  {active && (
                    <svg className="animate-spin w-3 h-3 text-brand-600 flex-shrink-0" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25"/>
                      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
                    </svg>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  // ── Error phase ─────────────────────────────────────────────────────────────
  if (phase === 'error') {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center p-6">
        <div className="w-full max-w-sm text-center">
          <img src={logo} alt="ShopIQ" className="w-12 h-12 object-contain mx-auto mb-6" />
          <div className="w-14 h-14 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
          </div>
          <h2 className="text-lg font-bold text-zinc-900 mb-2">Scan failed</h2>
          <p className="text-sm text-zinc-500 mb-6">{errorMsg}</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => { setPhase('checking'); startScan() }}
              className="bg-brand-600 hover:bg-brand-800 text-white text-sm font-medium px-5 py-2.5 rounded-xl transition-colors"
            >
              Try again
            </button>
            <button
              onClick={goToDashboard}
              className="bg-zinc-100 hover:bg-zinc-100 text-zinc-700 text-sm font-medium px-5 py-2.5 rounded-xl transition-colors"
            >
              Skip to dashboard
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Result phase ─────────────────────────────────────────────────────────────
  const deadPct = result && result.total_inventory_value > 0
    ? Math.round((result.dead_stock_value / result.total_inventory_value) * 100)
    : 0

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-6">
      <div className="w-full max-w-lg">

        {/* Header */}
        <div className="text-center mb-8">
          <img src={logo} alt="ShopIQ" className="w-10 h-10 object-contain mx-auto mb-4 opacity-80" />
          <p className="text-zinc-400 text-sm font-medium uppercase tracking-widest mb-2">Your store scan is complete</p>
          <h1 className="text-3xl sm:text-4xl font-bold text-white leading-tight">
            Here's what we found
          </h1>
        </div>

        {/* Dead stock hero number */}
        <div className="bg-white rounded-3xl p-8 mb-4 text-center shadow-2xl">
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-3">Cash tied up in dead stock</p>
          <p className="text-5xl sm:text-6xl font-bold text-brand-600 mb-2">
            {result ? fmt(result.dead_stock_value, result.currency) : '—'}
          </p>
          <p className="text-sm text-zinc-500">
            Across <span className="font-semibold text-zinc-700">{result?.skus_dead_stock ?? 0} SKUs</span> that haven't moved in 90+ days
            {deadPct > 0 && (
              <> — <span className="font-semibold text-red-500">{deadPct}%</span> of your total inventory value</>
            )}
          </p>
        </div>

        {/* Secondary stats */}
        <div className="grid grid-cols-2 gap-3 mb-8">
          <div className="bg-zinc-800 rounded-2xl p-5 text-center">
            <p className="text-2xl font-bold text-white mb-1">
              {result ? fmt(result.total_inventory_value, result.currency) : '—'}
            </p>
            <p className="text-xs text-zinc-400">Total inventory value</p>
          </div>
          <div className="bg-amber-500/20 border border-amber-500/30 rounded-2xl p-5 text-center">
            <p className="text-2xl font-bold text-amber-400 mb-1">{result?.skus_urgent ?? 0}</p>
            <p className="text-xs text-amber-300/80">SKUs at risk of stockout</p>
          </div>
        </div>

        {/* Share card */}
        <div className="mb-6">
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-3">
            Share your results
          </p>
          {result && (
            <ShareCard
              deadStockValue={result.dead_stock_value}
              skusDeadStock={result.skus_dead_stock}
              totalInventoryValue={result.total_inventory_value}
              skusUrgent={result.skus_urgent}
              currency={result.currency}
              shopDomain={result.shop_domain}
            />
          )}
        </div>

        {/* What else is ready */}
        <div className="bg-zinc-800/60 rounded-2xl p-5 mb-6">
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-3">Also ready in your dashboard</p>
          <div className="space-y-2">
            {[
              { label: 'Product SEO & content audit', icon: '📋' },
              { label: 'Return abuse detection', icon: '↩️' },
              { label: 'Competitor price gaps', icon: '💰' },
              { label: 'AI product description rewrites', icon: '✍️' },
            ].map(item => (
              <div key={item.label} className="flex items-center gap-3">
                <span className="text-base">{item.icon}</span>
                <span className="text-sm text-zinc-300">{item.label}</span>
                <span className="ml-auto text-[10px] font-semibold bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full">Ready</span>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <button
          onClick={goToDashboard}
          className="w-full bg-brand-600 hover:bg-brand-800 text-white font-bold py-4 rounded-2xl transition-colors text-base flex items-center justify-center gap-2"
        >
          View Full Inventory Report
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
          </svg>
        </button>
        <p className="text-center text-xs text-zinc-500 mt-3">
          Your full dashboard is ready — inventory, returns, SEO, pricing, and AI tools
        </p>
      </div>
    </div>
  )
}
