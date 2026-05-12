import { useState, useRef } from 'react'
import logo from '../assets/shopiq-lettermark-1200.png'

// ── Install form ──────────────────────────────────────────────────────────────

function ShopInstallForm({ backendUrl, large }: { backendUrl: string; large?: boolean }) {
  const [shop, setShop] = useState('')
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleInstall = () => {
    const raw = shop.trim().toLowerCase().replace(/\.myshopify\.com$/, '')
    if (!raw) { setError('Please enter your store name.'); inputRef.current?.focus(); return }
    if (!/^[a-z0-9-]+$/.test(raw)) { setError('Store name can only contain letters, numbers, and hyphens.'); return }
    setError('')
    window.location.href = `${backendUrl}/auth/shopify/install?shop=${raw}.myshopify.com`
  }

  return (
    <div className="space-y-2">
      <div className={`flex rounded overflow-hidden border bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-700 focus-within:border-brand-400 dark:focus-within:border-brand-300 focus-within:ring-1 focus-within:ring-brand-300/50 transition-all`}>
        <input
          ref={inputRef}
          type="text"
          value={shop}
          onChange={e => { setShop(e.target.value); setError('') }}
          onKeyDown={e => e.key === 'Enter' && handleInstall()}
          placeholder="your-store-name"
          className={`flex-1 px-4 ${large ? 'py-3 text-base' : 'py-2.5 text-sm'} text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-600 outline-none bg-transparent`}
          autoComplete="off"
          spellCheck={false}
        />
        <span className={`flex items-center px-3 text-zinc-400 dark:text-zinc-600 ${large ? 'text-sm' : 'text-xs'} border-l border-zinc-200 dark:border-zinc-700 select-none whitespace-nowrap bg-zinc-50 dark:bg-zinc-800/50`}>
          .myshopify.com
        </span>
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <button
        onClick={handleInstall}
        className={`w-full bg-brand-200 hover:bg-brand-300 text-brand-900 font-semibold rounded transition-colors flex items-center justify-center gap-2 ${large ? 'py-3 text-base' : 'py-2.5 text-sm'}`}
      >
        Install ShopIQ Free
      </button>
      <p className="text-xs text-zinc-400 text-center">Free forever — no credit card required</p>
    </div>
  )
}

// ── Dev launcher ──────────────────────────────────────────────────────────────

function DevLauncher({ backendUrl }: { backendUrl: string }) {
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState<'idle' | 'login' | 'seeding' | 'done' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  const handleDevLaunch = async () => {
    setLoading(true); setStep('login'); setErrorMsg('')
    try {
      let loginRes: Response
      try {
        loginRes = await fetch(`${backendUrl}/dev/login`, { credentials: 'include' })
      } catch {
        throw new Error('Cannot connect to local backend on port 8000. Make sure "python dev_server.py" is running.')
      }
      if (!loginRes.ok) throw new Error(`Login failed (${loginRes.status}): ${await loginRes.text()}`)
      await loginRes.json()
      setStep('seeding')
      const seedRes = await fetch(`${backendUrl}/dev/seed-audit`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' } })
      if (!seedRes.ok) throw new Error(`Seed failed (${seedRes.status}): ${await seedRes.text()}`)
      const data = await seedRes.json()
      if (!data.audit_id) throw new Error('No audit_id in response')
      localStorage.setItem('shopiq_active_audit', data.audit_id)
      setStep('done')
      setTimeout(() => { window.location.href = '/dashboard' }, 600)
    } catch (err: any) {
      setStep('error'); setErrorMsg(err?.message ?? 'Unknown error')
    } finally { setLoading(false) }
  }

  const Spinner = () => (
    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25"/>
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
    </svg>
  )

  const stepLabel: Record<string, string> = {
    idle: '⚡ Launch with mock data', login: 'Creating demo session…',
    seeding: 'Running audit on 12 products…', done: '✓ Opening dashboard…', error: '↺ Try again',
  }

  return (
    <div className="rounded border border-brand-200/40 dark:border-brand-300/20 bg-brand-50 dark:bg-brand-200/5 p-4 mb-5">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] font-bold bg-brand-200 dark:bg-brand-200/20 text-brand-800 dark:text-brand-300 px-2 py-0.5 rounded tracking-wide uppercase">Dev mode</span>
        <span className="text-xs text-brand-700 dark:text-brand-400 font-medium">No Shopify account needed</span>
      </div>
      <p className="text-xs text-brand-600 dark:text-brand-400/80 mb-3 leading-relaxed">
        Loads 12 realistic products, runs the full audit engine, and opens the dashboard pre-populated.
      </p>
      {step === 'error' && (
        <div className="mb-3 bg-red-950/30 border border-red-900/40 rounded px-3 py-2.5">
          <p className="text-xs font-medium text-red-400 mb-1">Launch failed</p>
          <p className="text-xs text-red-400/80 break-all">{errorMsg}</p>
        </div>
      )}
      {step !== 'idle' && step !== 'error' && (
        <div className="mb-3 space-y-2">
          {(['login', 'seeding', 'done'] as const).map((s, i) => {
            const idx = ['login', 'seeding', 'done'].indexOf(step)
            const done = i < idx || step === 'done'
            const active = i === idx && step !== 'done'
            const labels = ['Creating demo session', 'Running audit on 12 products', 'Opening dashboard']
            return (
              <div key={s} className="flex items-center gap-2">
                <div className={`w-4 h-4 rounded-full flex-shrink-0 flex items-center justify-center text-[10px] font-bold ${done ? 'bg-emerald-500 text-white' : active ? 'bg-brand-300 text-brand-900' : 'bg-zinc-200 dark:bg-zinc-700 text-zinc-400'}`}>
                  {done ? '✓' : i + 1}
                </div>
                <span className={`text-xs flex-1 ${done ? 'text-emerald-500' : active ? 'text-brand-600 dark:text-brand-300 font-medium' : 'text-zinc-400'}`}>
                  {labels[i]}{active ? '…' : ''}
                </span>
                {active && <Spinner />}
              </div>
            )
          })}
        </div>
      )}
      <button
        onClick={() => { if (step === 'error') { setStep('idle'); setErrorMsg('') } handleDevLaunch() }}
        disabled={loading || step === 'done'}
        className="w-full bg-brand-200 dark:bg-brand-200/15 text-brand-900 dark:text-brand-200 text-sm font-medium py-2.5 rounded hover:bg-brand-300 dark:hover:bg-brand-200/25 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
      >
        {loading && <Spinner />}
        {stepLabel[step]}
      </button>
      <p className="text-[10px] text-zinc-400 mt-2 text-center font-mono">
        Requires <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">python dev_server.py</code> on port 8000
      </p>
    </div>
  )
}

// ── Feature card ──────────────────────────────────────────────────────────────

function FeatureCard({ icon, title, description, badge }: {
  icon: React.ReactNode; title: string; description: string; badge?: string
}) {
  return (
    <div className="rounded border border-zinc-100 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 hover:border-zinc-200 dark:hover:border-zinc-700 transition-colors">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded bg-brand-50 dark:bg-brand-200/10 flex items-center justify-center flex-shrink-0 text-brand-600 dark:text-brand-300">
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-zinc-800 dark:text-zinc-200 text-sm">{title}</h3>
            {badge && <span className="text-[10px] font-bold bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 px-2 py-0.5 rounded-full">{badge}</span>}
          </div>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed">{description}</p>
        </div>
      </div>
    </div>
  )
}

// ── Main landing page ─────────────────────────────────────────────────────────

export function LoginPage() {
  const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  const BACKEND_URL = isDev ? 'http://localhost:8000' : 'https://shopiq-production.up.railway.app'

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-[#09090b]">

      {/* Nav */}
      <nav className="border-b border-zinc-100 dark:border-zinc-800/80 bg-white/90 dark:bg-zinc-950/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded bg-brand-200 dark:bg-brand-200/15 flex items-center justify-center">
              <img src={logo} alt="ShopIQ" className="w-5 h-5 object-contain" />
            </div>
            <span className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm tracking-tight">ShopIQ</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#features" className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors hidden sm:block">Features</a>
            <a href="#pricing" className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors hidden sm:block">Pricing</a>
            <a href="#install" className="bg-brand-200 hover:bg-brand-300 text-brand-900 text-sm font-medium px-4 py-1.5 rounded transition-colors">
              Install Free
            </a>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 bg-brand-50 dark:bg-brand-200/8 border border-brand-200 dark:border-brand-300/20 rounded-full px-4 py-1.5 mb-8">
          <span className="w-1.5 h-1.5 bg-brand-400 dark:bg-brand-300 rounded-full animate-pulse" />
          <span className="text-xs font-medium text-brand-700 dark:text-brand-300">Free to install — no credit card required</span>
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold text-zinc-900 dark:text-zinc-50 leading-tight mb-6 tracking-tight">
          Find out exactly how much cash<br className="hidden sm:block" />
          <span className="text-brand-600 dark:text-brand-300"> is sitting dead in your store</span>
        </h1>
        <p className="text-lg text-zinc-500 dark:text-zinc-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          ShopIQ scans your Shopify store and surfaces what Shopify's built-in analytics won't tell you —
          dead inventory, return abuse, SEO gaps, and competitor pricing — in under 2 minutes.
        </p>

        <div id="install" className="max-w-md mx-auto">
          {isDev && <DevLauncher backendUrl={BACKEND_URL} />}
          <ShopInstallForm backendUrl={BACKEND_URL} large />
          {isDev && <p className="text-[10px] text-zinc-400 mt-2 font-mono">Backend: {BACKEND_URL}</p>}
        </div>
      </section>

      {/* Stats bar */}
      <section className="bg-white dark:bg-zinc-900 border-y border-zinc-100 dark:border-zinc-800 py-10">
        <div className="max-w-5xl mx-auto px-6 grid grid-cols-2 sm:grid-cols-4 gap-8 text-center">
          {[
            { value: '6',    label: 'Intelligence modules' },
            { value: '18+',  label: 'Audit rules per product' },
            { value: '2 min',label: 'First scan time' },
            { value: 'Free', label: 'To get started' },
          ].map(s => (
            <div key={s.label}>
              <p className="text-3xl font-bold text-brand-600 dark:text-brand-300 mb-1">{s.value}</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Problem section */}
      <section className="max-w-5xl mx-auto px-6 py-20">
        <div className="text-center mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold text-zinc-900 dark:text-zinc-100 mb-4 tracking-tight">
            Shopify's analytics won't tell you this
          </h2>
          <p className="text-zinc-500 dark:text-zinc-400 max-w-xl mx-auto">
            You can see revenue and traffic. But the problems quietly bleeding your store are invisible by default.
          </p>
        </div>
        <div className="grid sm:grid-cols-2 gap-3 max-w-3xl mx-auto">
          {[
            { q: 'Which products are tying up my cash?', sub: 'Dead stock builds silently. Most owners find out too late.' },
            { q: 'Which product pages are hurting my SEO?', sub: 'Thin descriptions and missing meta tags cost you organic traffic every day.' },
            { q: 'Are my prices higher than my competitors?', sub: 'A 15% price gap can tank conversion on your best SKUs without a single alert.' },
            { q: 'Who keeps gaming my return policy?', sub: 'A handful of customers can account for 40%+ of your total refunds.' },
          ].map(item => (
            <div key={item.q} className="flex gap-3 bg-white dark:bg-zinc-900 rounded border border-zinc-100 dark:border-zinc-800 p-4">
              <div className="w-5 h-5 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-red-500 dark:text-red-400 text-xs font-bold">✕</span>
              </div>
              <div>
                <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mb-0.5">{item.q}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">{item.sub}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="text-center mt-8 text-sm font-semibold text-brand-600 dark:text-brand-300">ShopIQ answers all of these — automatically.</p>
      </section>

      {/* Features */}
      <section id="features" className="bg-white dark:bg-zinc-900 border-y border-zinc-100 dark:border-zinc-800 py-20">
        <div className="max-w-5xl mx-auto px-6">
          <div className="text-center mb-12">
            <h2 className="text-2xl sm:text-3xl font-bold text-zinc-900 dark:text-zinc-100 mb-4 tracking-tight">Everything in one dashboard</h2>
            <p className="text-zinc-500 dark:text-zinc-400 max-w-xl mx-auto">
              Six tools most Shopify stores pay for separately — unified into one install.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <FeatureCard badge="Most popular" title="StockSense — Inventory Intelligence"
              description="See exactly how much cash is locked in dead stock. Get days-to-stockout predictions, capital efficiency scores, and reorder recommendations per SKU."
              icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>}
            />
            <FeatureCard title="ShopAudit AI — Store Health Scorer"
              description="Scores every product 0–100 across SEO, content quality, UX, and catalogue completeness. Flags critical issues with AI-powered rewrite suggestions."
              icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>}
            />
            <FeatureCard title="ReturnRadar — Return Abuse Detection"
              description="Identifies serial returners, tracks return rates per product, and surfaces repeat refund patterns before they compound into a real cash drain."
              icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.01"/></svg>}
            />
            <FeatureCard title="PricePulse — Competitor Price Monitoring"
              description="Live competitor price data per product. See exactly where you're overpriced or getting undercut, with % gap alerts on your top SKUs."
              icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>}
            />
            <FeatureCard title="BulkCopy AI — Description Generator"
              description="AI rewrites weak product descriptions at scale. Filter by low-scoring products, edit in-place, then push directly back to Shopify in one click."
              icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>}
            />
            <FeatureCard title="ReviewReply Pro — Automated Responses"
              description="Generate on-brand replies to customer reviews in bulk. Edit, approve, and post — no more copy-pasting the same response 30 times a week."
              icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>}
            />
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-5xl mx-auto px-6 py-20">
        <div className="text-center mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold text-zinc-900 dark:text-zinc-100 mb-4 tracking-tight">Simple pricing</h2>
          <p className="text-zinc-500 dark:text-zinc-400">Start free. Upgrade when it's worth it.</p>
        </div>
        <div className="grid sm:grid-cols-3 gap-4">
          {[
            { name: 'Free',       price: '$0',   period: 'forever',  desc: "See what's broken before committing",   features: ['10 audits / month', '10 AI copy rewrites', '10 AI fixes', '1 store', 'All 6 modules'],                            cta: 'Get started free', highlight: false },
            { name: 'Pro',        price: '$29',  period: '/month',   desc: 'For stores serious about fixing leaks', features: ['100 audits / month', '200 AI copy rewrites', '200 AI fixes', '1 store', 'Full catalog scans', 'Complete history'], cta: 'Start Pro',        highlight: true  },
            { name: 'Enterprise', price: '$199', period: '/month',   desc: 'For agencies and multi-store operators',features: ['Unlimited everything', 'Up to 10 stores', 'Priority support', 'All Pro features'],                               cta: 'Start Enterprise', highlight: false },
          ].map(plan => (
            <div
              key={plan.name}
              className={`rounded border p-6 flex flex-col ${
                plan.highlight
                  ? 'border-brand-300 dark:border-brand-300/40 bg-brand-600 dark:bg-brand-200/10 ring-1 ring-brand-300/30'
                  : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900'
              }`}
            >
              <div className="mb-4">
                <p className={`text-[11px] font-bold uppercase tracking-widest mb-2 ${plan.highlight ? 'text-brand-200' : 'text-zinc-400'}`}>{plan.name}</p>
                <div className="flex items-baseline gap-1 mb-1">
                  <span className={`text-3xl font-bold tracking-tight ${plan.highlight ? 'text-white' : 'text-zinc-900 dark:text-zinc-100'}`}>{plan.price}</span>
                  <span className={`text-sm ${plan.highlight ? 'text-brand-200' : 'text-zinc-400'}`}>{plan.period}</span>
                </div>
                <p className={`text-sm ${plan.highlight ? 'text-brand-100' : 'text-zinc-500 dark:text-zinc-400'}`}>{plan.desc}</p>
              </div>
              <ul className="space-y-2 mb-6 flex-1">
                {plan.features.map(f => (
                  <li key={f} className="flex items-center gap-2 text-sm">
                    <span className={`text-xs ${plan.highlight ? 'text-brand-200' : 'text-emerald-500 dark:text-emerald-400'}`}>✓</span>
                    <span className={plan.highlight ? 'text-brand-100' : 'text-zinc-600 dark:text-zinc-400'}>{f}</span>
                  </li>
                ))}
              </ul>
              <a
                href="#install"
                className={`text-center text-sm font-semibold py-2.5 rounded transition-colors ${
                  plan.highlight
                    ? 'bg-brand-200 text-brand-900 hover:bg-brand-300'
                    : 'bg-zinc-900 dark:bg-zinc-700 text-white hover:bg-zinc-700 dark:hover:bg-zinc-600'
                }`}
              >
                {plan.cta}
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="bg-zinc-900 dark:bg-zinc-950 border-t border-zinc-800 py-20">
        <div className="max-w-xl mx-auto px-6 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-4 tracking-tight">
            See your dead stock number in 2 minutes
          </h2>
          <p className="text-zinc-400 mb-8 text-sm leading-relaxed">
            Free install. No credit card. Connect your store and ShopIQ runs your first scan automatically.
          </p>
          <div className="bg-zinc-900 dark:bg-zinc-900 rounded border border-zinc-700 p-6">
            <ShopInstallForm backendUrl={BACKEND_URL} large />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-zinc-100 dark:border-zinc-800 py-8">
        <div className="max-w-5xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-brand-200 dark:bg-brand-200/15 flex items-center justify-center">
              <img src={logo} alt="ShopIQ" className="w-3.5 h-3.5 object-contain" />
            </div>
            <span className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">ShopIQ</span>
            <span className="text-xs text-zinc-400">by SHOPIQ SOFTWARES, LLC</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="https://shopiq-production.up.railway.app/privacy" target="_blank" rel="noopener noreferrer" className="text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors">Privacy Policy</a>
          </div>
        </div>
      </footer>
    </div>
  )
}
