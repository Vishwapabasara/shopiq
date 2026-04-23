import { useState } from 'react'
import { PriceProduct } from '../../lib/api'

interface Props {
  products: PriceProduct[]
  currency: string
}

type Filter = 'all' | 'overpriced' | 'undercut' | 'competitive' | 'no_data'

const STATUS_CFG = {
  overpriced:  { label: 'Overpriced',  bg: 'bg-red-50',     text: 'text-red-700',     border: 'border-red-100'    },
  undercut:    { label: 'Undercut',    bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-100'  },
  competitive: { label: 'Competitive', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-100'},
  no_data:     { label: 'No Data',     bg: 'bg-slate-50',   text: 'text-slate-500',   border: 'border-slate-100'  },
}

function fmt(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(n)
}

export function PriceTable({ products, currency }: Props) {
  const [filter, setFilter] = useState<Filter>('all')
  const [expanded, setExpanded] = useState<string | null>(null)

  const counts = {
    all: products.length,
    overpriced: products.filter(p => p.status === 'overpriced').length,
    undercut:   products.filter(p => p.status === 'undercut').length,
    competitive:products.filter(p => p.status === 'competitive').length,
    no_data:    products.filter(p => p.status === 'no_data').length,
  }

  const filtered = filter === 'all'
    ? products
    : products.filter(p => p.status === filter)

  // Sort: overpriced first, then undercut, then competitive
  const ORDER: Record<string, number> = { overpriced: 0, undercut: 1, competitive: 2, no_data: 3 }
  const sorted = [...filtered].sort((a, b) =>
    (ORDER[a.status] ?? 9) - (ORDER[b.status] ?? 9) ||
    (b.price_gap_pct ?? 0) - (a.price_gap_pct ?? 0)
  )

  const TABS: { key: Filter; label: string }[] = [
    { key: 'all',        label: `All (${counts.all})` },
    { key: 'overpriced', label: `Overpriced (${counts.overpriced})` },
    { key: 'undercut',   label: `Undercut (${counts.undercut})` },
    { key: 'competitive',label: `Competitive (${counts.competitive})` },
    { key: 'no_data',    label: `No Data (${counts.no_data})` },
  ]

  return (
    <div className="card overflow-hidden">
      {/* Tabs */}
      <div className="px-5 pt-4 pb-0 border-b border-slate-100">
        <div className="flex gap-0 overflow-x-auto">
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              className={`px-3 py-2 text-xs font-medium whitespace-nowrap border-b-2 transition-colors -mb-px ${
                filter === t.key
                  ? 'border-brand-600 text-brand-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-xs text-slate-400 font-medium uppercase tracking-wide">
              <th className="text-left px-5 py-2.5">Product</th>
              <th className="text-right px-3 py-2.5 whitespace-nowrap">Our Price</th>
              <th className="text-right px-3 py-2.5 whitespace-nowrap">Mkt Min</th>
              <th className="text-right px-3 py-2.5 whitespace-nowrap">Gap</th>
              <th className="text-right px-3 py-2.5 whitespace-nowrap">Suggestion</th>
              <th className="text-center px-3 py-2.5">Status</th>
              <th className="text-center px-3 py-2.5 whitespace-nowrap">Sources</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {sorted.map(p => {
              const s = STATUS_CFG[p.status]
              const isExpanded = expanded === p.product_id
              const gapColor =
                (p.price_gap_pct ?? 0) > 10 ? 'text-red-600 font-semibold' :
                (p.price_gap_pct ?? 0) > 3  ? 'text-amber-500 font-medium' :
                (p.price_gap_pct ?? 0) < -5 ? 'text-emerald-600' : 'text-slate-500'

              return (
                <>
                  <tr
                    key={p.product_id}
                    className="hover:bg-slate-50 transition-colors cursor-pointer"
                    onClick={() => setExpanded(isExpanded ? null : p.product_id)}
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-slate-100 flex-shrink-0 flex items-center justify-center overflow-hidden">
                          {p.image_url
                            ? <img src={p.image_url} alt="" className="w-full h-full object-cover" />
                            : <span className="text-slate-400 text-xs">◉</span>
                          }
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-slate-800 truncate max-w-[180px]">{p.title}</p>
                          <p className="text-[10px] text-slate-400 truncate max-w-[180px]">{p.search_query}</p>
                        </div>
                        <span className="text-slate-300 text-xs ml-1">{isExpanded ? '▲' : '▼'}</span>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums font-medium text-slate-700">
                      {fmt(p.our_price)}
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums text-slate-600">
                      {p.min_competitor_price ? fmt(p.min_competitor_price) : <span className="text-slate-300">—</span>}
                    </td>
                    <td className={`px-3 py-3 text-right tabular-nums ${gapColor}`}>
                      {p.price_gap_pct !== null
                        ? `${p.price_gap_pct > 0 ? '+' : ''}${p.price_gap_pct.toFixed(1)}%`
                        : <span className="text-slate-300">—</span>
                      }
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums">
                      {p.suggested_price
                        ? <span className="text-emerald-600 font-medium">{fmt(p.suggested_price)}</span>
                        : <span className="text-slate-300">—</span>
                      }
                    </td>
                    <td className="px-3 py-3 text-center">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${s.bg} ${s.text} ${s.border}`}>
                        {s.label}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-center text-slate-500 font-medium">
                      {p.competitors_count > 0 ? p.competitors_count : <span className="text-slate-300">—</span>}
                    </td>
                  </tr>

                  {/* Expanded competitor row */}
                  {isExpanded && p.competitor_prices.length > 0 && (
                    <tr key={`${p.product_id}-expanded`} className="bg-slate-50">
                      <td colSpan={7} className="px-5 py-3">
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                          Competitor prices found for "{p.search_query}"
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {p.competitor_prices.map((c, i) => (
                            <a
                              key={i}
                              href={c.url || '#'}
                              target={c.url ? '_blank' : '_self'}
                              rel="noopener noreferrer"
                              onClick={e => !c.url && e.preventDefault()}
                              className="flex items-center gap-2 bg-white border border-slate-200 rounded-lg px-3 py-2 hover:border-slate-300 transition-colors"
                            >
                              <span className="text-xs font-medium text-slate-700">{c.competitor}</span>
                              <span className={`text-xs font-bold tabular-nums ${
                                c.price < p.our_price ? 'text-red-600' : 'text-slate-500'
                              }`}>{fmt(c.price)}</span>
                              {c.availability === 'in_stock'
                                ? <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" title="In stock" />
                                : <span className="w-1.5 h-1.5 rounded-full bg-slate-300" title="Out of stock" />
                              }
                            </a>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
