import { useState } from 'react'
import { StockProduct } from '../../lib/api'

interface Props {
  products: StockProduct[]
  currency: string
  filterStatus: string | null
}

const STATUS_CONFIG = {
  urgent:     { label: 'Urgent',     bg: 'bg-red-50',     text: 'text-red-700',     border: 'border-red-100'    },
  healthy:    { label: 'Healthy',    bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-100' },
  monitor:    { label: 'Monitor',    bg: 'bg-blue-50',    text: 'text-blue-700',    border: 'border-blue-100'   },
  dead_stock: { label: 'Dead Stock', bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-100'  },
}

const ABC_CONFIG = {
  A: 'bg-violet-100 text-violet-700',
  B: 'bg-sky-100 text-sky-700',
  C: 'bg-slate-100 text-slate-500',
}

const TREND_ICON = {
  rising:  { icon: '↑', cls: 'text-emerald-600' },
  falling: { icon: '↓', cls: 'text-red-500' },
  stable:  { icon: '→', cls: 'text-slate-400' },
}

function fmt(n: number, currency: string) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency, maximumFractionDigits: 0,
  }).format(n)
}

type SortKey = 'status' | 'days_to_stockout' | 'revenue_at_risk' | 'daily_velocity' | 'inventory_qty'

export function StockTable({ products, currency, filterStatus }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('status')
  const [sortAsc, setSortAsc] = useState(true)
  const [page, setPage] = useState(0)
  const PAGE = 15

  const filtered = filterStatus
    ? products.filter(p => p.status === filterStatus)
    : products

  const sorted = [...filtered].sort((a, b) => {
    const statusOrder = { urgent: 0, monitor: 1, dead_stock: 2, healthy: 3 }
    if (sortKey === 'status') {
      return sortAsc
        ? (statusOrder[a.status] ?? 9) - (statusOrder[b.status] ?? 9)
        : (statusOrder[b.status] ?? 9) - (statusOrder[a.status] ?? 9)
    }
    const av = a[sortKey] ?? (sortAsc ? Infinity : -Infinity)
    const bv = b[sortKey] ?? (sortAsc ? Infinity : -Infinity)
    return sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number)
  })

  const pages = Math.ceil(sorted.length / PAGE)
  const visible = sorted.slice(page * PAGE, page * PAGE + PAGE)

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc(!sortAsc)
    else { setSortKey(key); setSortAsc(true) }
    setPage(0)
  }

  function SortBtn({ k, children }: { k: SortKey; children: React.ReactNode }) {
    return (
      <button
        onClick={() => toggleSort(k)}
        className="flex items-center gap-0.5 hover:text-slate-800 transition-colors"
      >
        {children}
        {sortKey === k && <span className="text-brand-600">{sortAsc ? '↑' : '↓'}</span>}
      </button>
    )
  }

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
        <p className="text-sm font-semibold text-slate-800">
          {filterStatus
            ? `${STATUS_CONFIG[filterStatus as keyof typeof STATUS_CONFIG]?.label ?? filterStatus} — ${filtered.length} SKU${filtered.length !== 1 ? 's' : ''}`
            : `All SKUs — ${products.length}`
          }
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-xs text-slate-400 font-medium uppercase tracking-wide">
              <th className="text-left px-5 py-2.5 w-full max-w-xs">Product</th>
              <th className="text-right px-3 py-2.5 whitespace-nowrap">
                <SortBtn k="inventory_qty">Stock</SortBtn>
              </th>
              <th className="text-right px-3 py-2.5 whitespace-nowrap">
                <SortBtn k="days_to_stockout">Days left</SortBtn>
              </th>
              <th className="text-right px-3 py-2.5 whitespace-nowrap">
                <SortBtn k="daily_velocity">Velocity</SortBtn>
              </th>
              <th className="text-right px-3 py-2.5 whitespace-nowrap">
                <SortBtn k="revenue_at_risk">RAR</SortBtn>
              </th>
              <th className="text-center px-3 py-2.5">Status</th>
              <th className="text-center px-3 py-2.5">ABC</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {visible.map(p => {
              const s = STATUS_CONFIG[p.status] ?? STATUS_CONFIG.healthy
              const trend = TREND_ICON[p.velocity_trend]
              const daysColor =
                p.days_to_stockout === null ? 'text-slate-300' :
                p.days_to_stockout <= 7 ? 'text-red-600 font-semibold' :
                p.days_to_stockout <= 14 ? 'text-amber-500 font-medium' :
                p.days_to_stockout <= 30 ? 'text-blue-600' : 'text-slate-500'

              return (
                <tr key={p.variant_id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-slate-100 flex-shrink-0 flex items-center justify-center overflow-hidden">
                        {p.image_url
                          ? <img src={p.image_url} alt="" className="w-full h-full object-cover" />
                          : <span className="text-slate-400 text-xs">⬡</span>
                        }
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-800 truncate max-w-[200px]">{p.title}</p>
                        <p className="text-xs text-slate-400">{p.sku || '—'}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">
                    <span className="text-slate-700 font-medium">{p.inventory_qty}</span>
                  </td>
                  <td className={`px-3 py-3 text-right tabular-nums ${daysColor}`}>
                    {p.days_to_stockout !== null ? `${p.days_to_stockout}d` : '—'}
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">
                    <span className="text-slate-700">{p.daily_velocity.toFixed(1)}</span>
                    <span className={`ml-1 text-xs font-bold ${trend.cls}`}>{trend.icon}</span>
                    <span className="block text-[10px] text-slate-400">units/day</span>
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">
                    {p.revenue_at_risk > 0
                      ? <span className="text-red-600 font-medium">{fmt(p.revenue_at_risk, currency)}</span>
                      : <span className="text-slate-300">—</span>
                    }
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${s.bg} ${s.text} ${s.border}`}>
                      {s.label}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${ABC_CONFIG[p.abc_class]}`}>
                      {p.abc_class}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between">
          <span className="text-xs text-slate-400">
            {page * PAGE + 1}–{Math.min((page + 1) * PAGE, sorted.length)} of {sorted.length}
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-2.5 py-1 text-xs rounded border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
            >
              ←
            </button>
            <button
              onClick={() => setPage(p => Math.min(pages - 1, p + 1))}
              disabled={page >= pages - 1}
              className="px-2.5 py-1 text-xs rounded border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
            >
              →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
