import { StockAnalysisResults } from '../../lib/api'

interface Props {
  results: StockAnalysisResults
}

function fmt(n: number, currency: string) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency, maximumFractionDigits: 0,
  }).format(n)
}

export function StockOverview({ results }: Props) {
  const c = results.currency || 'USD'

  const effColor =
    results.capital_efficiency >= 80 ? 'text-emerald-600' :
    results.capital_efficiency >= 60 ? 'text-amber-500' : 'text-red-600'

  return (
    <div className="space-y-4">
      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-4">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1">Revenue at Risk</p>
          <p className={`text-2xl font-semibold tabular-nums ${results.total_revenue_at_risk > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
            {fmt(results.total_revenue_at_risk, c)}
          </p>
          <p className="text-xs text-slate-400 mt-0.5">Next 14 days · {results.skus_urgent} urgent SKU{results.skus_urgent !== 1 ? 's' : ''}</p>
        </div>

        <div className="card p-4">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1">Dead Stock Value</p>
          <p className={`text-2xl font-semibold tabular-nums ${results.dead_stock_value > 1000 ? 'text-amber-500' : 'text-slate-700'}`}>
            {fmt(results.dead_stock_value, c)}
          </p>
          <p className="text-xs text-slate-400 mt-0.5">{results.skus_dead_stock} SKU{results.skus_dead_stock !== 1 ? 's' : ''} not moving</p>
        </div>

        <div className="card p-4">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1">Avg. Days Left</p>
          <p className={`text-2xl font-semibold tabular-nums ${results.avg_days_to_stockout < 7 ? 'text-red-600' : results.avg_days_to_stockout < 14 ? 'text-amber-500' : 'text-slate-700'}`}>
            {results.avg_days_to_stockout > 0 ? `${results.avg_days_to_stockout}d` : '—'}
          </p>
          <p className="text-xs text-slate-400 mt-0.5">Across {results.skus_urgent} at-risk SKUs</p>
        </div>

        <div className="card p-4">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1">Capital Efficiency</p>
          <p className={`text-2xl font-semibold tabular-nums ${effColor}`}>
            {results.capital_efficiency.toFixed(0)}%
          </p>
          <p className="text-xs text-slate-400 mt-0.5">{fmt(results.total_inventory_value, c)} total stock value</p>
        </div>
      </div>

      {/* Insights */}
      {results.insights.length > 0 && (
        <div className="card px-5 py-4">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Key Insights</p>
          <ul className="space-y-2">
            {results.insights.map((insight, i) => (
              <li key={i} className="flex gap-2.5 text-sm text-slate-700">
                <span className="mt-0.5 flex-shrink-0 w-4 h-4 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-[10px] font-bold">
                  {i + 1}
                </span>
                {insight}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
