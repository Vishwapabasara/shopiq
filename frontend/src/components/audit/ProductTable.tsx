import { useState } from 'react'
import { SeverityBadge, Spinner } from '../ui'
import { scoreColor, severityDot, cn } from '../../lib/utils'
import { useAuditResults } from '../../hooks/useAudit'

const SEVERITY_FILTERS = [
  { value: '',         label: 'All products' },
  { value: 'critical', label: 'Critical'     },
  { value: 'warning',  label: 'Warnings'     },
  { value: 'info',     label: 'Info'         },
]

const SORT_OPTIONS = [
  { value: 'score_asc',  label: 'Worst first'  },
  { value: 'score_desc', label: 'Best first'   },
  { value: 'alpha',      label: 'A → Z'        },
]

interface Props {
  auditId: string
  onSelectProduct: (productId: string) => void
}

export function ProductTable({ auditId, onSelectProduct }: Props) {
  const [severity, setSeverity] = useState('')
  const [sort, setSort] = useState('score_asc')
  const [offset, setOffset] = useState(0)
  const LIMIT = 25

  const { data, isLoading } = useAuditResults(auditId, {
    severity: severity || undefined,
    sort,
    limit: LIMIT,
    offset,
  })

  const products = data?.product_results ?? []
  const total = data?.total_products ?? 0
  const pagination = data ? { total, has_more: offset + LIMIT < total } : undefined

  return (
    <div className="card overflow-hidden">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 px-5 py-4 border-b border-slate-100">
        <h3 className="text-sm font-semibold text-slate-800 mr-auto">Product results</h3>

        {/* Severity filter pills */}
        <div className="flex gap-1.5">
          {SEVERITY_FILTERS.map(f => (
            <button
              key={f.value}
              onClick={() => { setSeverity(f.value); setOffset(0) }}
              className={cn(
                'text-xs px-3 py-1.5 rounded-full border transition-colors',
                severity === f.value
                  ? 'bg-brand-600 text-white border-brand-600'
                  : 'text-slate-600 border-slate-200 hover:border-slate-300 bg-white'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Sort */}
        <select
          value={sort}
          onChange={e => { setSort(e.target.value); setOffset(0) }}
          className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-600 bg-white"
        >
          {SORT_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex justify-center py-16"><Spinner size={24} /></div>
      ) : products.length === 0 ? (
        <div className="text-center py-16 text-slate-400 text-sm">No products match this filter</div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Product</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide w-20">Score</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Top issue</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide w-28">Severity</th>
                  <th className="px-4 py-3 w-16" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {products.map(p => {
                  const topIssue = p.issues?.find(i => i.severity === 'critical')
                    ?? p.issues?.find(i => i.severity === 'warning')
                    ?? p.issues?.[0]

                  return (
                    <tr
                      key={p.shopify_product_id}
                      className="hover:bg-slate-50/60 transition-colors cursor-pointer group"
                      onClick={() => onSelectProduct(p.shopify_product_id)}
                    >
                      <td className="px-5 py-3.5">
                        <span className="font-medium text-slate-800 group-hover:text-brand-700 transition-colors">
                          {p.title}
                        </span>
                        <div className="flex gap-3 mt-0.5">
                          <span className="text-xs text-slate-400">{p.image_count} images</span>
                          <span className="text-xs text-slate-400">{p.word_count} words</span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={cn('text-lg font-semibold tabular-nums', scoreColor(p.score))}>
                          {p.score}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        {topIssue ? (
                          <div className="flex items-start gap-2">
                            <div className={cn('w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0', severityDot(topIssue.severity))} />
                            <span className="text-slate-600 text-xs leading-relaxed">{topIssue.message}</span>
                          </div>
                        ) : (
                          <span className="text-emerald-600 text-xs font-medium">✓ No issues</span>
                        )}
                      </td>
                      <td className="px-4 py-3.5">
                        {topIssue && <SeverityBadge severity={topIssue.severity} />}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <button className="text-xs text-brand-600 font-medium opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                          View →
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {pagination && (pagination.has_more || offset > 0) && (
            <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100 bg-slate-50/50">
              <span className="text-xs text-slate-500">
                Showing {offset + 1}–{Math.min(offset + LIMIT, total)} of {total}
              </span>
              <div className="flex gap-2">
                <button
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - LIMIT))}
                  className="text-xs px-3 py-1.5 border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-white transition-colors"
                >
                  ← Prev
                </button>
                <button
                  disabled={!pagination.has_more}
                  onClick={() => setOffset(offset + LIMIT)}
                  className="text-xs px-3 py-1.5 border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-white transition-colors"
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
