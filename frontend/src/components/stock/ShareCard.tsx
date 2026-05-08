import { useRef, useState } from 'react'
import html2canvas from 'html2canvas'

interface ShareCardProps {
  deadStockValue: number
  skusDeadStock: number
  totalInventoryValue: number
  skusUrgent: number
  currency: string
  shopDomain?: string
}

function fmt(n: number, currency: string) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(n)
}

// ── The visual card (this is what gets captured) ──────────────────────────────

function Card({ deadStockValue, skusDeadStock, totalInventoryValue, skusUrgent, currency, shopDomain }: ShareCardProps) {
  const deadPct = totalInventoryValue > 0
    ? Math.round((deadStockValue / totalInventoryValue) * 100)
    : 0

  const storeName = shopDomain
    ? shopDomain.replace('.myshopify.com', '')
    : 'Your Store'

  return (
    <div
      style={{
        width: 600,
        background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)',
        borderRadius: 24,
        padding: '40px 44px',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        color: '#fff',
        boxSizing: 'border-box',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 32, height: 32, background: '#4f46e5',
            borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, fontWeight: 800, color: '#fff',
          }}>S</div>
          <span style={{ fontWeight: 700, fontSize: 16, color: '#e2e8f0' }}>ShopIQ</span>
        </div>
        <span style={{ fontSize: 12, color: '#64748b', background: '#1e293b', padding: '4px 12px', borderRadius: 20 }}>
          Store Intelligence Report
        </span>
      </div>

      {/* Store name */}
      <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600 }}>
        {storeName}
      </p>

      {/* Divider */}
      <div style={{ height: 1, background: 'linear-gradient(90deg, #4f46e5, transparent)', marginBottom: 28 }} />

      {/* Hero label */}
      <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 12, fontWeight: 500 }}>
        Cash locked in dead inventory
      </p>

      {/* Hero number */}
      <div style={{ marginBottom: 10 }}>
        <span style={{
          fontSize: 64,
          fontWeight: 800,
          color: '#ffffff',
          letterSpacing: '-2px',
          lineHeight: 1,
        }}>
          {fmt(deadStockValue, currency)}
        </span>
      </div>

      {/* Subtitle */}
      <p style={{ fontSize: 15, color: '#a5b4fc', marginBottom: 32, fontWeight: 500 }}>
        {skusDeadStock} SKUs haven't sold in 90+ days
        {deadPct > 0 && ` · ${deadPct}% of total stock value`}
      </p>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 32 }}>
        <div style={{
          flex: 1, background: 'rgba(255,255,255,0.06)',
          borderRadius: 14, padding: '16px 20px',
          border: '1px solid rgba(255,255,255,0.08)',
        }}>
          <p style={{ fontSize: 11, color: '#64748b', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Total Inventory
          </p>
          <p style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0' }}>
            {fmt(totalInventoryValue, currency)}
          </p>
        </div>
        <div style={{
          flex: 1, background: 'rgba(245,158,11,0.1)',
          borderRadius: 14, padding: '16px 20px',
          border: '1px solid rgba(245,158,11,0.2)',
        }}>
          <p style={{ fontSize: 11, color: '#92400e', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#d97706' }}>
            At Risk of Stockout
          </p>
          <p style={{ fontSize: 22, fontWeight: 700, color: '#fbbf24' }}>
            {skusUrgent} SKUs
          </p>
        </div>
      </div>

      {/* Footer */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        paddingTop: 20, borderTop: '1px solid rgba(255,255,255,0.06)',
      }}>
        <p style={{ fontSize: 12, color: '#475569' }}>
          Free scan at <span style={{ color: '#818cf8' }}>shopiq-iota.vercel.app</span>
        </p>
        <div style={{
          fontSize: 11, color: '#4f46e5',
          background: 'rgba(79,70,229,0.15)',
          padding: '4px 10px', borderRadius: 20,
          border: '1px solid rgba(79,70,229,0.3)',
          fontWeight: 600,
        }}>
          Powered by ShopIQ
        </div>
      </div>
    </div>
  )
}

// ── Export wrapper with download / copy buttons ───────────────────────────────

export function ShareCard(props: ShareCardProps) {
  const cardRef = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<'idle' | 'capturing' | 'done' | 'copied'>('idle')

  const capture = async (): Promise<HTMLCanvasElement | null> => {
    if (!cardRef.current) return null
    return html2canvas(cardRef.current, {
      scale: 2,
      useCORS: true,
      backgroundColor: null,
      logging: false,
    })
  }

  const handleDownload = async () => {
    setStatus('capturing')
    try {
      const canvas = await capture()
      if (!canvas) return
      const link = document.createElement('a')
      link.download = `shopiq-dead-stock-report.png`
      link.href = canvas.toDataURL('image/png')
      link.click()
      setStatus('done')
      setTimeout(() => setStatus('idle'), 2000)
    } catch {
      setStatus('idle')
    }
  }

  const handleCopy = async () => {
    setStatus('capturing')
    try {
      const canvas = await capture()
      if (!canvas) return
      canvas.toBlob(async (blob) => {
        if (!blob) return
        await navigator.clipboard.write([
          new ClipboardItem({ 'image/png': blob }),
        ])
        setStatus('copied')
        setTimeout(() => setStatus('idle'), 2000)
      })
    } catch {
      setStatus('idle')
    }
  }

  const busy = status === 'capturing'

  return (
    <div className="space-y-4">
      {/* Card preview */}
      <div
        ref={cardRef}
        className="rounded-3xl overflow-hidden"
        style={{ width: 600, maxWidth: '100%' }}
      >
        <Card {...props} />
      </div>

      {/* Action buttons */}
      <div className="flex gap-3">
        <button
          onClick={handleDownload}
          disabled={busy}
          className="flex-1 flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-800 disabled:opacity-50 text-white text-sm font-semibold py-2.5 rounded-xl transition-colors"
        >
          {busy ? (
            <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25"/>
              <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          )}
          {status === 'done' ? 'Downloaded!' : 'Download PNG'}
        </button>

        <button
          onClick={handleCopy}
          disabled={busy}
          className="flex-1 flex items-center justify-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white text-sm font-semibold py-2.5 rounded-xl transition-colors"
        >
          {status === 'copied' ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          )}
          {status === 'copied' ? 'Copied!' : 'Copy Image'}
        </button>
      </div>

      <p className="text-xs text-slate-500 text-center">
        Share on Reddit, Twitter, or LinkedIn to show what you found
      </p>
    </div>
  )
}
