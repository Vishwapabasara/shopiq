import { PriceAnalysisResults } from '../../lib/api'

interface Props {
  results: PriceAnalysisResults
}

export function PriceOverview({ results }: Props) {
  const checked = results.total_products - results.products_no_data
  const undercutPct  = checked ? Math.round(results.products_undercut   / checked * 100) : 0
  const overpricedPct= checked ? Math.round(results.products_overpriced / checked * 100) : 0
  const compPct      = checked ? Math.round(results.products_competitive / checked * 100) : 0

  return (
    <div className="space-y-4">
      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-4">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1">Products Checked</p>
          <p className="text-2xl font-semibold tabular-nums text-slate-800">{results.total_products}</p>
          <p className="text-xs text-slate-400 mt-0.5">Against live market prices</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1">Overpriced</p>
          <p className={`text-2xl font-semibold tabular-nums ${results.products_overpriced > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
            {results.products_overpriced}
          </p>
          <p className="text-xs text-slate-400 mt-0.5">Significantly above market</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1">Being Undercut</p>
          <p className={`text-2xl font-semibold tabular-nums ${results.products_undercut > 0 ? 'text-amber-500' : 'text-emerald-600'}`}>
            {results.products_undercut}
          </p>
          <p className="text-xs text-slate-400 mt-0.5">Competitors slightly cheaper</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1">Competitive</p>
          <p className="text-2xl font-semibold tabular-nums text-emerald-600">{results.products_competitive}</p>
          <p className="text-xs text-slate-400 mt-0.5">Well priced vs market</p>
        </div>
      </div>

      {/* Market position distribution */}
      <div className="card px-5 py-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold text-slate-800">Market Position Distribution</p>
          <p className="text-xs text-slate-400">{checked} products with competitor data</p>
        </div>
        <div className="flex h-3 rounded-full overflow-hidden gap-0.5 mb-3">
          {overpricedPct > 0 && (
            <div className="bg-red-400 transition-all duration-700" style={{ width: `${overpricedPct}%` }} title={`Overpriced: ${overpricedPct}%`} />
          )}
          {undercutPct > 0 && (
            <div className="bg-amber-400 transition-all duration-700" style={{ width: `${undercutPct}%` }} title={`Undercut: ${undercutPct}%`} />
          )}
          {compPct > 0 && (
            <div className="bg-emerald-400 transition-all duration-700" style={{ width: `${compPct}%` }} title={`Competitive: ${compPct}%`} />
          )}
          {results.products_no_data > 0 && (
            <div
              className="bg-slate-200 transition-all duration-700"
              style={{ width: `${Math.round(results.products_no_data / results.total_products * 100)}%` }}
              title={`No data: ${results.products_no_data}`}
            />
          )}
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-slate-500">
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-400" />{overpricedPct}% overpriced</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-400" />{undercutPct}% undercut</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-400" />{compPct}% competitive</span>
          {results.products_no_data > 0 && (
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-slate-300" />{results.products_no_data} no data</span>
          )}
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

      {/* Top competitors */}
      {results.top_competitors.length > 0 && (
        <div className="card px-5 py-4">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Top Competitors Across Your Catalogue</p>
          <div className="flex flex-wrap gap-2">
            {results.top_competitors.map(c => (
              <div key={c.name} className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5">
                <span className="text-sm font-medium text-slate-700">{c.name}</span>
                <span className="text-xs text-slate-400">{c.count} product{c.count !== 1 ? 's' : ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
