import { useProductDetail } from '../../hooks/useAudit'
import { SeverityBadge, Spinner, ScoreRing } from '../ui'
import { categoryLabel, scoreLabel, cn } from '../../lib/utils'

interface Props {
  auditId: string
  productId: string | null
  onClose: () => void
}

export function ProductDrawer({ auditId, productId, onClose }: Props) {
  const { data: product, isLoading } = useProductDetail(
    auditId,
    productId,
  )

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
          <div className="flex-1 min-w-0 pr-4">
            <h2 className="font-semibold text-slate-800 text-base truncate">
              {product?.title ?? 'Loading…'}
            </h2>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">{product?.handle}</p>
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
            <div className="flex justify-center py-12"><Spinner size={28} /></div>
          )}

          {product && (
            <>
              {/* Score + meta */}
              <div className="flex items-center gap-6">
                <ScoreRing score={product.score} size={96} strokeWidth={7} />
                <div className="space-y-1.5">
                  <p className="text-sm font-semibold text-slate-700">{scoreLabel(product.score)}</p>
                  <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                    <span className="bg-slate-100 rounded px-2 py-0.5">{product.image_count} images</span>
                    <span className="bg-slate-100 rounded px-2 py-0.5">{product.word_count} words</span>
                    <span className={cn('rounded px-2 py-0.5',
                      product.has_seo_title ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                    )}>
                      SEO title {product.has_seo_title ? '✓' : '✗'}
                    </span>
                    <span className={cn('rounded px-2 py-0.5',
                      product.has_meta_description ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                    )}>
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

              {/* Issues list */}
              {(product.issues?.length ?? 0) > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                    Issues found ({product.issues?.length ?? 0})
                  </h3>
                  <div className="space-y-2">
                    {product.issues?.map((issue, i) => (
                      <div
                        key={i}
                        className={cn(
                          'rounded-lg p-3.5 border',
                          issue.severity === 'critical' ? 'bg-red-50 border-red-100' :
                          issue.severity === 'warning'  ? 'bg-amber-50 border-amber-100' :
                                                          'bg-blue-50 border-blue-100'
                        )}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm font-medium text-slate-800">{issue.message}</p>
                          <SeverityBadge severity={issue.severity} />
                        </div>
                        <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">
                          <span className="font-medium text-slate-700">Fix: </span>
                          {issue.fix_hint}
                        </p>
                        <p className="text-[10px] text-slate-400 mt-1.5 font-mono">{issue.rule}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* AI improvements */}
              {(product.ai_improvements?.length ?? 0) > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                      AI recommendations
                    </h3>
                    <span className="text-[9px] bg-brand-50 text-brand-700 border border-brand-100 px-1.5 py-0.5 rounded font-medium">
                      GPT-4o
                    </span>
                    {product.ai_score !== null && (
                      <span className="text-xs text-slate-400 ml-auto">
                        Content quality: <strong className="text-slate-600">{product.ai_score}/100</strong>
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

              {/* AI rewrite */}
              {product.ai_rewrite && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                      AI-rewritten description
                    </h3>
                    <span className="text-[9px] bg-brand-50 text-brand-700 border border-brand-100 px-1.5 py-0.5 rounded font-medium">
                      GPT-4o
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
        <div className="border-t border-slate-100 px-6 py-4">
          <a
            href={`https://${window.location.hostname.replace(/^[^.]+\./, '')}/admin/products/${product?.shopify_product_id}`}
            target="_blank"
            rel="noreferrer"
            className="btn-primary w-full text-center block"
          >
            Edit in Shopify →
          </a>
        </div>
      </div>
    </>
  )
}
