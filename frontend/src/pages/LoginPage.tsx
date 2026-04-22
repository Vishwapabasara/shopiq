import { useState } from 'react'
import logo from '../assets/shopiq-lettermark-1200.png'

export function LoginPage() {
  const [shop, setShop] = useState('')
  const [shopError, setShopError] = useState('')
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState<'idle' | 'login' | 'seeding' | 'done' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'

  // CRITICAL: Always use full backend URL in production
  const BACKEND_URL = isDev 
    ? 'http://localhost:8000'
    : 'https://shopiq-production.up.railway.app'

  const handleDevLaunch = async () => {
    if (!isDev) {
      alert('Dev mode is only available when running locally')
      return
    }

    setLoading(true)
    setStep('login')
    setErrorMsg('')

    try {
      // Step 1: create session
      let loginRes: Response
      try {
        loginRes = await fetch(`${BACKEND_URL}/dev/login`, {
          credentials: 'include',
        })
      } catch (err) {
        throw new Error(
          'Cannot connect to local backend on port 8000. ' +
          'Make sure "python dev_server.py" is running.'
        )
      }

      if (!loginRes.ok) {
        const txt = await loginRes.text()
        throw new Error(`Login failed (${loginRes.status}): ${txt}`)
      }
      await loginRes.json()

      setStep('seeding')

      // Step 2: seed mock audit
      const seedRes = await fetch(`${BACKEND_URL}/dev/seed-audit`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })

      if (!seedRes.ok) {
        const txt = await seedRes.text()
        throw new Error(`Seed failed (${seedRes.status}): ${txt}`)
      }

      const data = await seedRes.json()
      if (!data.audit_id) throw new Error('No audit_id in response')

      localStorage.setItem('shopiq_active_audit', data.audit_id)
      setStep('done')
      setTimeout(() => { window.location.href = '/dashboard' }, 600)

    } catch (err: any) {
      setStep('error')
      setErrorMsg(err?.message ?? 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const handleInstall = () => {
    setLoading(true)
    setShopError('')

    const clean = shop.trim().toLowerCase()
      .replace(/^https?:\/\//, '')
      .replace(/\/$/, '')
    
    const domain = clean.endsWith('.myshopify.com') ? clean : `${clean}.myshopify.com`
    
    // Validate shop domain
    if (!/^[a-z0-9][a-z0-9\-]*\.myshopify\.com$/.test(domain)) {
      setShopError('Enter a valid Shopify store URL e.g. mystore.myshopify.com')
      setLoading(false)
      return
    }
    
    // CRITICAL: Redirect directly to backend (not relative URL)
    const installUrl = `${BACKEND_URL}/auth/shopify/install?shop=${domain}`
    
    console.log('🔗 Redirecting to backend:', installUrl)
    
    // Add small delay so user sees the loading state
    setTimeout(() => {
      window.location.href = installUrl
    }, 300)
  }

  const stepLabel: Record<string, string> = {
    idle:    '⚡ Launch with mock data',
    login:   'Creating demo session…',
    seeding: 'Running audit on 12 products…',
    done:    '✓ Opening dashboard…',
    error:   '↺ Try again',
  }

  const Spinner = () => (
    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25"/>
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
    </svg>
  )

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-4">

        {/* Logo */}
        <div className="flex flex-col items-center gap-2 mb-2">
          <img src={logo} alt="ShopIQ" className="w-20 h-20 object-contain" />
          <div className="text-center">
            <h1 className="font-semibold text-slate-900 text-lg leading-tight">ShopIQ</h1>
            <p className="text-xs text-slate-400">Shopify Intelligence Platform</p>
          </div>
        </div>

        {/* Dev card */}
        {isDev && (
          <div className="card p-5 border-brand-200 bg-brand-50">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-bold bg-brand-600 text-white px-2 py-0.5 rounded tracking-wide uppercase">
                Dev mode
              </span>
              <span className="text-xs text-brand-700 font-medium">No Shopify account needed</span>
            </div>
            <p className="text-xs text-brand-600 mb-3 leading-relaxed">
              Loads 12 realistic products, runs the full audit engine, and opens the dashboard pre-populated with results.
            </p>

            {/* Error */}
            {step === 'error' && (
              <div className="mb-3 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
                <p className="text-xs font-medium text-red-700 mb-1">Launch failed</p>
                <p className="text-xs text-red-600 break-all">{errorMsg}</p>
              </div>
            )}

            {/* Progress steps */}
            {step !== 'idle' && step !== 'error' && (
              <div className="mb-3 space-y-2">
                {(['login', 'seeding', 'done'] as const).map((s, i) => {
                  const idx = ['login', 'seeding', 'done'].indexOf(step)
                  const done = i < idx || step === 'done'
                  const active = i === idx && step !== 'done'
                  const labels = ['Creating demo session', 'Running audit on 12 products', 'Opening dashboard']
                  return (
                    <div key={s} className="flex items-center gap-2">
                      <div className={`w-4 h-4 rounded-full flex-shrink-0 flex items-center justify-center text-[10px] font-bold
                        ${done ? 'bg-emerald-500 text-white' : active ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-400'}`}>
                        {done ? '✓' : i + 1}
                      </div>
                      <span className={`text-xs flex-1 ${done ? 'text-emerald-700' : active ? 'text-brand-700 font-medium' : 'text-slate-400'}`}>
                        {labels[i]}{active ? '…' : ''}
                      </span>
                      {active && <Spinner />}
                    </div>
                  )
                })}
              </div>
            )}

            <button
              onClick={() => {
                if (step === 'error') {
                  setStep('idle')
                  setErrorMsg('')
                }
                handleDevLaunch()
              }}
              disabled={loading || step === 'done'}
              className="w-full bg-brand-600 text-white text-sm font-medium py-2.5 rounded-lg
                         hover:bg-brand-800 transition-colors disabled:opacity-60
                         flex items-center justify-center gap-2"
            >
              {loading && <Spinner />}
              {stepLabel[step]}
            </button>

            <p className="text-[10px] text-brand-400 mt-2 text-center">
              Requires <code className="bg-brand-100 px-1 rounded">python dev_server.py</code> running on port 8000
            </p>
          </div>
        )}

        {/* Real Shopify install */}
        <div className="card p-6 space-y-4">
          <div>
            <h2 className="font-semibold text-slate-800 mb-1">
              {isDev ? 'Or connect a real store' : 'Connect your store'}
            </h2>
            <p className="text-sm text-slate-500">Enter your Shopify store URL to install ShopIQ.</p>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1.5">Store URL</label>
            <div className="flex">
              <input
                type="text"
                value={shop}
                onChange={e => { setShop(e.target.value); setShopError('') }}
                onKeyDown={e => e.key === 'Enter' && !loading && handleInstall()}
                placeholder="mystore"
                disabled={loading}
                className="flex-1 border border-r-0 border-slate-200 rounded-l-lg px-3 py-2.5
                           text-sm focus:outline-none focus:border-brand-400 transition-colors
                           disabled:bg-slate-100 disabled:cursor-not-allowed"
              />
              <span className="border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm
                               text-slate-400 rounded-r-lg border-l-0 whitespace-nowrap">
                .myshopify.com
              </span>
            </div>
            {shopError && <p className="text-xs text-red-500 mt-1.5">{shopError}</p>}
          </div>
          <button 
            onClick={handleInstall} 
            disabled={loading || !shop.trim()}
            className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed
                       flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Spinner />
                Connecting...
              </>
            ) : (
              'Install ShopIQ →'
            )}
          </button>
          <p className="text-xs text-slate-400 text-center">
            Free audit up to 10 products. No credit card required.
          </p>
          
          {/* Debug info in dev */}
          {isDev && (
            <p className="text-[10px] text-slate-400 text-center font-mono">
              Backend: {BACKEND_URL}
            </p>
          )}
        </div>

      </div>
    </div>
  )
}