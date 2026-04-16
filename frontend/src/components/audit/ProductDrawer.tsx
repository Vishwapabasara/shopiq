import { useQuery } from '@tanstack/react-query'
import { useProductDetail } from '../../hooks/useAudit'
import { authApi } from '../../lib/api'
import { SeverityBadge, Spinner, ScoreRing } from '../ui'
import { categoryLabel, scoreLabel, cn } from '../../lib/utils'

interface Props {
  auditId: string
  productId: string | null
  onClose: () => void
}

// Inline progress bar for score breakdown (value out of max)
function ScoreBar({
  label,
  value,
  max = 50,
}: {
  label: string
  value: number
  max?: number
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  const color =
    pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-400' : 'bg-red-400'
  const textColor =
    pct >= 70 ? 'text-emerald-600' : pct >= 40 ? 'text-amber-500' : 'text-red-500'

  return (
    <div>
      <div className="flex justify-between items-center mb-1.5">
        <span className="text-sm text-slate-600">{label}</span>
        <span className={cn('text-sm font-semibold tabular-nums', textColor)}>
          {value}/{max}
        </span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-700', color)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// Group issues by severity for display
function groupBySeverity(issues: Array<{ severity: string; message: string; fix_hint?: string; rule?: string }>) {
  const order = ['critical', 'warning', 'info'] as const
  return order
    .map(sev => ({
      severity: sev,
      items: issues.filter(i => i.severity === sev),
    }))
    .filter(g => g.items.length > 0)
}

export function ProductDrawer({ auditId, productId, onClose }: Props) {
  const { data: product, isLoading } = useProductDetail(auditId, productId)
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: authApi.me })

  // Derive store name: "amba-storees.myshopify.com" → "amba-storees"
  const storeName = me?.shop_domain?.replace('.myshopify.com', '') ?? ''
  const shopifyProductUrl =
    storeName && product?.shopify_product_id
      ? `https://admin.shopify.com/store/${storeName}/products/${product.shopify_product_id}`
      : '#'

  const isOpen = !!productId

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          'fixed inset-0 bg-black/20 z-30 transition-opacity duration-200',
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        )}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={cn(
          'fixed top-0 right-0 h-full w-full max-w-xl bg-white shadow-2xl z-40',
          'flex flex-col transition-transform duration-300 ease-out',
          isOpen ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-5 border-b border-slate-100">
          <div className="flex items-center gap-3 flex-1 min-w-0 pr-4">
            {product?.image_url && (
              <img
                src={product.image_url}
                alt={product.title}
                className="w-12 h-12 rounded-lg object-cover flex-shrink-0 border border-slate-100"
              />
            )}
            <div className="min-w-0">
              <h2 className="font-semibold text-slate-800 text-base truncate">
                {product?.title ?? 'Loading…'}
              </h2>
              <p className="text-xs text-slate-400 mt-0.5 font-mono">{product?.handle}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 transition-colors text-xl leading-none flex-shrink-0"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
          {isLoading && (
            <div className="flex justify-center py-12">
              <Spinner size={28} />
            </div>
          )}

          {product && (
            <>
              {/* Overall score + metadata */}
              <div className="flex items-center gap-6">
                <ScoreRing score={product.score} size={96} strokeWidth={7} />
                <div className="space-y-1.5">
                  <p className="text-sm font-semibold text-slate-700">{scoreLabel(product.score)}</p>
                  <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                    <span className="bg-slate-100 rounded px-2 py-0.5">{product.image_count} images</span>
                    <span className="bg-slate-100 rounded px-2 py-0.5">{product.word_count} words</span>
                    <span
                      className={cn(
                        'rounded px-2 py-0.5',
                        product.has_seo_title
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-red-50 text-red-700'
                      )}
                    >
                      SEO title {product.has_seo_title ? '✓' : '✗'}
                    </span>
                    <span
                      className={cn(
                        'rounded px-2 py-0.5',
                        product.has_meta_description
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-red-50 text-red-700'
                      )}
                    >
                      Meta desc {product.has_meta_description ? '✓' : '✗'}
                    </span>
                  </div>
                  {product.ai_verdict && (
                    <p className="text-xs text-slate-500 italic mt-1 max-w-xs">
                      "{product.ai_verdict}"
                    </p>
                  )}
                </div>
              </div>

              {/* Score breakdown */}
              {(product.content_score !== undefined ||
                product.visual_score !== undefined ||
                product.title_score !== undefined) && (
                <div className="bg-slate-50 rounded-xl p-4 space-y-3">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                    Score breakdown
                  </h3>
                  {product.content_score !== undefined && (
                    <ScoreBar label="Content Quality" value={product.content_score} max={50} />
                  )}
                  {product.visual_score !== undefined && (
                    <ScoreBar label="Visual Appeal" value={product.visual_score} max={50} />
                  )}
                  {product.title_score !== undefined && (
                    <ScoreBar label="Title Optimization" value={product.title_score} max={50} />
                  )}
                </div>
              )}

              {/* Issues grouped by severity */}
              {(product.issues?.length ?? 0) > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                    Issues found ({product.issues?.length ?? 0})
                  </h3>
                  <div className="space-y-4">
                    {groupBySeverity(product.issues ?? []).map(({ severity, items }) => (
                      <div key={severity}>
                        <div className="flex items-center gap-2 mb-2">
                          <SeverityBadge severity={severity} />
                          <span className="text-xs text-slate-400">{items.length} issue{items.length !== 1 ? 's' : ''}</span>
                        </div>
                        <div className="space-y-2">
                          {items.map((issue, i) => (
                            <div
                              key={i}
                              className={cn(
                                'rounded-lg p-3.5 border',
                                severity === 'critical'
                                  ? 'bg-red-50 border-red-100'
                                  : severity === 'warning'
                                  ? 'bg-amber-50 border-amber-100'
                                  : 'bg-blue-50 border-blue-100'
                              )}
                            >
                              <p className="text-sm font-medium text-slate-800">{issue.message}</p>
                              {issue.fix_hint && (
                                <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">
                                  <span className="font-medium text-slate-700">Fix: </span>
                                  {issue.fix_hint}
                                </p>
                              )}
                              {issue.rule && (
                                <p className="text-[10px] text-slate-400 mt-1.5 font-mono">{issue.rule}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* AI recommendations */}
              {(product.ai_improvements?.length ?? 0) > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                      AI recommendations
                    </h3>
                    <span className="text-[9px] bg-brand-50 text-brand-700 border border-brand-100 px-1.5 py-0.5 rounded font-medium">
                      Gemini
                    </span>
                    {product.ai_score !== null && (
                      <span className="text-xs text-slate-400 ml-auto">
                        Content quality:{' '}
                        <strong className="text-slate-600">{product.ai_score}/100</strong>
                      </span>
                    )}
                  </div>
                  <ul className="space-y-2">
                    {product.ai_improvements?.map((imp, i) => (
                      <li key={i} className="flex items-start gap-2.5 text-sm text-slate-700">
                        <span className="mt-0.5 text-brand-500 text-xs font-bold flex-shrink-0">
                          {i + 1}.
                        </span>
                        {imp}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* AI rewritten description */}
              {product.ai_rewrite && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                      AI-rewritten description
                    </h3>
                    <span className="text-[9px] bg-brand-50 text-brand-700 border border-brand-100 px-1.5 py-0.5 rounded font-medium">
                      Gemini
                    </span>
                  </div>
                  <div
                    className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm text-slate-700 leading-relaxed prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: product.ai_rewrite }}
                  />
                  <button
                    onClick={() => navigator.clipboard.writeText(product.ai_rewrite ?? '')}
                    className="mt-2 text-xs text-brand-600 hover:text-brand-800 font-medium transition-colors"
                  >
                    Copy to clipboard →
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-100 px-6 py-4 flex gap-3">
          <a
            href={shopifyProductUrl}
            target="_blank"
            rel="noreferrer"
            className="btn-primary flex-1 text-center block"
          >
            Fix in Shopify →
          </a>
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </>
  )
}
