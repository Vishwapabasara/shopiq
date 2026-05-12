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
      <div className="flex flex-wrap items-center gap-3 px-5 py-4 border-b border-zinc-100 dark:border-zinc-800">
        <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mr-auto">Product results</h3>

        {/* Severity filter pills */}
        <div className="flex gap-1.5">
          {SEVERITY_FILTERS.map(f => (
            <button
              key={f.value}
              onClick={() => { setSeverity(f.value); setOffset(0) }}
              className={cn(
                'text-xs px-3 py-1.5 rounded-full border transition-colors',
                severity === f.value
                  ? 'bg-brand-200 text-brand-900 border-brand-200'
                  : 'text-zinc-600 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600 bg-white dark:bg-zinc-900'
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
          className="text-xs border border-zinc-200 dark:border-zinc-700 rounded px-2.5 py-1.5 text-zinc-600 dark:text-zinc-400 bg-white dark:bg-zinc-900"
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
        <div className="text-center py-16 text-zinc-400 text-sm">No products match this filter</div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-zinc-50 dark:bg-zinc-800/50 border-b border-zinc-100 dark:border-zinc-800">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">Product</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide w-20">Score</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">Top issue</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide w-28">Severity</th>
                  <th className="px-4 py-3 w-16" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-50 dark:divide-zinc-800">
                {products.map(p => {
                  const topIssue = p.issues?.find(i => i.severity === 'critical')
                    ?? p.issues?.find(i => i.severity === 'warning')
                    ?? p.issues?.[0]

                  return (
                    <tr
                      key={p.shopify_product_id}
                      className="hover:bg-zinc-50/60 dark:hover:bg-zinc-800/40 transition-colors cursor-pointer group"
                      onClick={() => onSelectProduct(p.shopify_product_id)}
                    >
                      <td className="px-5 py-3.5">
                        <span className="font-medium text-zinc-800 dark:text-zinc-200 group-hover:text-brand-700 dark:group-hover:text-brand-300 transition-colors">
                          {p.title}
                        </span>
                        <div className="flex gap-3 mt-0.5">
                          <span className="text-xs text-zinc-400">{p.image_count} images</span>
                          <span className="text-xs text-zinc-400">{p.word_count} words</span>
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
                            <span className="text-zinc-600 dark:text-zinc-400 text-xs leading-relaxed">{topIssue.message}</span>
                          </div>
                        ) : (
                          <span className="text-emerald-600 text-xs font-medium">✓ No issues</span>
                        )}
                      </td>
                      <td className="px-4 py-3.5">
                        {topIssue && <SeverityBadge severity={topIssue.severity} />}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <button className="text-xs text-brand-600 dark:text-brand-300 font-medium opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
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
            <div className="flex items-center justify-between px-5 py-3 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50">
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                Showing {offset + 1}–{Math.min(offset + LIMIT, total)} of {total}
              </span>
              <div className="flex gap-2">
                <button
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - LIMIT))}
                  className="text-xs px-3 py-1.5 border border-zinc-200 dark:border-zinc-700 rounded disabled:opacity-40 hover:bg-white dark:hover:bg-zinc-800 transition-colors"
                >
                  ← Prev
                </button>
                <button
                  disabled={!pagination.has_more}
                  onClick={() => setOffset(offset + LIMIT)}
                  className="text-xs px-3 py-1.5 border border-zinc-200 dark:border-zinc-700 rounded disabled:opacity-40 hover:bg-white dark:hover:bg-zinc-800 transition-colors"
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
