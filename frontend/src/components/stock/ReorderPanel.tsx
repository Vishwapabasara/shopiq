import { StockProduct } from '../../lib/api'

interface Props {
  products: StockProduct[]
  currency: string
}

function fmt(n: number, currency: string) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(n)
}

export function ReorderPanel({ products, currency }: Props) {
  const urgent = products
    .filter(p => p.status === 'urgent' || (p.status === 'monitor' && p.reorder_qty > 0))
    .sort((a, b) => (b.revenue_at_risk || 0) - (a.revenue_at_risk || 0))
    .slice(0, 8)

  if (urgent.length === 0) return null

  return (
    <div className="card px-5 py-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-sm font-semibold text-slate-800">Reorder Recommendations</p>
          <p className="text-xs text-slate-400 mt-0.5">Prioritised by revenue at risk</p>
        </div>
        <span className="text-xs font-medium bg-red-50 text-red-700 border border-red-100 px-2 py-1 rounded-full">
          {urgent.filter(p => p.status === 'urgent').length} urgent
        </span>
      </div>

      <div className="space-y-2">
        {urgent.map(p => {
          const isUrgent = p.status === 'urgent'
          const daysLeft = p.days_to_stockout !== null
            ? `${p.days_to_stockout}d left`
            : '< 30d velocity'
          return (
            <div
              key={p.variant_id}
              className={`flex items-center gap-4 px-4 py-3 rounded-lg border ${
                isUrgent ? 'bg-red-50 border-red-100' : 'bg-blue-50 border-blue-100'
              }`}
            >
              {/* Product */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800 truncate">{p.title}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {p.inventory_qty} units · {daysLeft} · {p.daily_velocity.toFixed(1)}/day
                </p>
              </div>

              {/* RAR */}
              {p.revenue_at_risk > 0 && (
                <div className="text-right flex-shrink-0">
                  <p className="text-xs text-red-600 font-semibold">{fmt(p.revenue_at_risk, currency)}</p>
                  <p className="text-[10px] text-slate-400">at risk</p>
                </div>
              )}

              {/* Reorder qty */}
              <div className={`text-right flex-shrink-0 min-w-[64px] px-3 py-1.5 rounded-lg ${
                isUrgent ? 'bg-red-100' : 'bg-blue-100'
              }`}>
                <p className={`text-base font-bold tabular-nums ${isUrgent ? 'text-red-700' : 'text-blue-700'}`}>
                  +{p.reorder_qty}
                </p>
                <p className={`text-[10px] ${isUrgent ? 'text-red-500' : 'text-blue-500'}`}>units</p>
              </div>
            </div>
          )
        })}
      </div>

      <p className="mt-3 text-[10px] text-slate-400">
        * Reorder quantities are calculated using a 7-day assumed lead time + 30-day safety buffer.
      </p>
    </div>
  )
}
