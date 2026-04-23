import { PriceProduct } from '../../lib/api'

interface Props {
  products: PriceProduct[]
  currency: string
}

function fmt(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(n)
}

const STATUS_CFG = {
  overpriced: {
    label: 'Overpriced',
    bg: 'bg-red-50', border: 'border-red-200',
    badge: 'bg-red-100 text-red-700 border-red-100',
    gapColor: 'text-red-600',
    desc: 'Significantly above market',
  },
  undercut: {
    label: 'Being Undercut',
    bg: 'bg-amber-50', border: 'border-amber-200',
    badge: 'bg-amber-100 text-amber-700 border-amber-100',
    gapColor: 'text-amber-600',
    desc: 'Competitors slightly cheaper',
  },
}

export function PriceAlerts({ products, currency }: Props) {
  const alerts = products
    .filter(p => p.status === 'overpriced' || p.status === 'undercut')
    .sort((a, b) => (b.price_gap_pct ?? 0) - (a.price_gap_pct ?? 0))

  if (alerts.length === 0) return null

  return (
    <div className="card px-5 py-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-sm font-semibold text-slate-800">Price Alerts</p>
          <p className="text-xs text-slate-400 mt-0.5">Products losing competitiveness — sorted by gap size</p>
        </div>
        <span className="text-xs font-medium bg-red-50 text-red-700 border border-red-100 px-2 py-1 rounded-full">
          {alerts.length} alert{alerts.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="space-y-3">
        {alerts.map(p => {
          const cfg = STATUS_CFG[p.status as keyof typeof STATUS_CFG]
          const cheapestComp = p.competitor_prices
            .filter(c => c.price === p.min_competitor_price)[0]
          return (
            <div key={p.product_id} className={`rounded-xl border px-4 py-3 ${cfg.bg} ${cfg.border}`}>
              <div className="flex items-start gap-4">
                {/* Product info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <p className="text-sm font-medium text-slate-800 truncate">{p.title}</p>
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${cfg.badge}`}>
                      {cfg.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-500 flex-wrap">
                    <span>Our price: <strong className="text-slate-700">{fmt(p.our_price)}</strong></span>
                    {p.min_competitor_price && (
                      <span>
                        Cheapest: <strong className="text-slate-700">{fmt(p.min_competitor_price)}</strong>
                        {cheapestComp && <span className="text-slate-400"> ({cheapestComp.competitor})</span>}
                      </span>
                    )}
                    {p.price_gap_pct !== null && (
                      <span className={`font-semibold ${cfg.gapColor}`}>
                        {p.price_gap_pct > 0 ? '+' : ''}{p.price_gap_pct.toFixed(1)}% vs market
                      </span>
                    )}
                  </div>
                  {/* Competitor list */}
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {p.competitor_prices.slice(0, 4).map((c, i) => (
                      <span key={i} className="text-[10px] bg-white border border-slate-200 rounded px-1.5 py-0.5 text-slate-600">
                        {c.competitor}: <strong>{fmt(c.price)}</strong>
                      </span>
                    ))}
                  </div>
                </div>

                {/* Suggestion */}
                {p.suggested_price && (
                  <div className="flex-shrink-0 text-right">
                    <p className="text-[10px] text-slate-400 mb-0.5">Suggested</p>
                    <p className="text-base font-bold text-emerald-600 tabular-nums">{fmt(p.suggested_price)}</p>
                    <p className="text-[10px] text-slate-400">
                      save {fmt(p.our_price - p.suggested_price)}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
