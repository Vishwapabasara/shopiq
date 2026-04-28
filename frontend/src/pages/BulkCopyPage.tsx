import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { copyApi, CopyProductResult, CopySession } from '../lib/api'
import { Spinner } from '../components/ui'

// ── Helpers ───────────────────────────────────────────────────────────────────

function stripHtml(html: string): string {
  return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

// ── Score delta badge ─────────────────────────────────────────────────────────

function ScoreDelta({ current, predicted }: { current: number | null; predicted: number }) {
  const delta = current !== null ? predicted - current : null
  const color = predicted >= 75 ? 'text-emerald-600' : predicted >= 50 ? 'text-amber-600' : 'text-red-600'
  return (
    <span className="flex items-center gap-1.5 text-xs font-medium tabular-nums">
      {current !== null && (
        <>
          <span className="text-slate-400">{current}</span>
          <span className="text-slate-300">→</span>
        </>
      )}
      <span className={color}>{predicted}</span>
      {delta !== null && (
        <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${delta > 0 ? 'bg-emerald-50 text-emerald-600' : delta < 0 ? 'bg-red-50 text-red-500' : 'bg-slate-100 text-slate-400'}`}>
          {delta > 0 ? '+' : ''}{delta}
        </span>
      )}
    </span>
  )
}

// ── Status badge ──────────────────────────────────────────────────────────────

const STATUS_STYLE: Record<string, string> = {
  pending:  'bg-slate-100 text-slate-500',
  approved: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  rejected: 'bg-red-50 text-red-600',
  pushed:   'bg-brand-50 text-brand-700 border border-brand-200',
  failed:   'bg-red-100 text-red-700',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full capitalize ${STATUS_STYLE[status] ?? STATUS_STYLE.pending}`}>
      {status}
    </span>
  )
}

// ── Product review row ────────────────────────────────────────────────────────

function ProductReviewRow({
  product,
  selected,
  localStatus,
  sessionId,
  onToggleSelect,
  onStatusChange,
}: {
  product: CopyProductResult
  selected: boolean
  localStatus: 'pending' | 'approved' | 'rejected'
  sessionId: string
  onToggleSelect: () => void
  onStatusChange: (status: 'approved' | 'rejected') => void
}) {
  const qc = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(
    product.edited_description ?? product.generated_description
  )

  const displayStatus = product.status === 'pushed' || product.status === 'failed'
    ? product.status
    : localStatus

  const saveEdit = useMutation({
    mutationFn: () =>
      copyApi.editProduct(sessionId, product.product_id, editText),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['copy', 'results', sessionId] })
      setEditing(false)
      onStatusChange('approved')
    },
  })

  const activeDescription = product.edited_description ?? product.generated_description
  const isPushed = product.status === 'pushed'

  return (
    <>
      <tr className={`border-b border-slate-100 transition-colors ${localStatus === 'rejected' ? 'opacity-40' : 'hover:bg-slate-50/60'}`}>
        <td className="px-4 py-3 w-10">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            disabled={localStatus === 'rejected' || isPushed}
            className="w-4 h-4 rounded accent-brand-600 cursor-pointer"
          />
        </td>
        <td className="px-3 py-3 w-12">
          {product.image_url
            ? <img src={product.image_url} alt="" className="w-10 h-10 rounded-lg object-cover" />
            : <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center text-slate-300 text-xl">◻</div>
          }
        </td>
        <td className="px-3 py-3 min-w-[160px] max-w-[220px]">
          <p className="text-sm font-medium text-slate-800 truncate">{product.title}</p>
          <p className="text-xs text-slate-400 truncate">{product.handle}</p>
        </td>
        <td className="px-3 py-3 w-32">
          <ScoreDelta current={product.current_score} predicted={product.predicted_score} />
        </td>
        <td className="px-3 py-3 w-24">
          <StatusBadge status={displayStatus} />
        </td>
        <td className="px-4 py-3 text-right">
          <div className="flex items-center justify-end gap-1.5">
            {!isPushed && (
              <>
                {localStatus !== 'approved' && (
                  <button
                    onClick={() => onStatusChange('approved')}
                    className="text-[11px] px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 font-medium transition-colors"
                  >
                    Approve
                  </button>
                )}
                {localStatus !== 'rejected' && (
                  <button
                    onClick={() => onStatusChange('rejected')}
                    className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-100 text-slate-500 hover:bg-red-50 hover:text-red-600 font-medium transition-colors"
                  >
                    Reject
                  </button>
                )}
              </>
            )}
            <button
              onClick={() => setExpanded(e => !e)}
              className="text-[11px] px-2.5 py-1 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 font-medium transition-colors flex items-center gap-1"
            >
              Diff
              <span className={`inline-block transition-transform duration-150 ${expanded ? 'rotate-180' : ''}`}>▾</span>
            </button>
          </div>
        </td>
      </tr>

      {expanded && (
        <tr className="bg-slate-50/80 border-b border-slate-100">
          <td colSpan={6} className="px-5 py-4">
            <div className="grid grid-cols-2 gap-4">
              {/* ── Current ── */}
              <div>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Current</p>
                <div className="bg-white border border-slate-200 rounded-xl p-3.5 text-sm text-slate-500 leading-relaxed min-h-[100px]">
                  {stripHtml(product.current_description) || (
                    <span className="italic text-slate-300">No description</span>
                  )}
                </div>
              </div>

              {/* ── AI Generated ── */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">AI Generated</p>
                  {!editing && !isPushed && (
                    <button
                      onClick={() => { setEditing(true); setEditText(activeDescription) }}
                      className="text-[11px] text-brand-600 hover:text-brand-700 font-medium flex items-center gap-0.5"
                    >
                      Edit ✎
                    </button>
                  )}
                </div>

                {editing ? (
                  <div>
                    <textarea
                      value={editText}
                      onChange={e => setEditText(e.target.value)}
                      rows={6}
                      className="w-full border border-brand-300 rounded-xl p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-200 font-mono resize-none"
                    />
                    <div className="flex gap-2 mt-2">
                      <button
                        onClick={() => saveEdit.mutate()}
                        disabled={saveEdit.isPending}
                        className="text-xs px-3 py-1.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 font-medium flex items-center gap-1"
                      >
                        {saveEdit.isPending ? <Spinner size={12} /> : null}
                        Save & Approve
                      </button>
                      <button
                        onClick={() => setEditing(false)}
                        className="text-xs px-3 py-1.5 border border-slate-200 text-slate-500 rounded-lg hover:bg-slate-50"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div
                    className="bg-white border border-emerald-200 rounded-xl p-3.5 text-sm text-slate-700 leading-relaxed min-h-[100px] prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: activeDescription }}
                  />
                )}

                {product.key_improvements?.length > 0 && !editing && (
                  <div className="mt-2 space-y-1">
                    {product.key_improvements.map((imp, i) => (
                      <p key={i} className="text-[11px] text-emerald-600 flex gap-1.5">
                        <span className="flex-shrink-0">✓</span>
                        <span>{imp}</span>
                      </p>
                    ))}
                  </div>
                )}

                {(product.seo_title || product.meta_description) && !editing && (
                  <div className="mt-3 px-3 py-2 bg-slate-50 rounded-lg border border-slate-100 space-y-1">
                    {product.seo_title && (
                      <p className="text-[11px]">
                        <span className="text-slate-400 font-semibold">SEO title: </span>
                        <span className="text-slate-600">{product.seo_title}</span>
                      </p>
                    )}
                    {product.meta_description && (
                      <p className="text-[11px]">
                        <span className="text-slate-400 font-semibold">Meta desc: </span>
                        <span className="text-slate-600">{product.meta_description}</span>
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ── Setup card ────────────────────────────────────────────────────────────────

function SetupCard({ onStart }: { onStart: (cfg: { filter_mode: string; max_products: number }) => void }) {
  const [filterMode, setFilterMode] = useState<'low_score' | 'all'>('low_score')
  const [maxProducts, setMaxProducts] = useState(20)
  const [loading, setLoading] = useState(false)

  function handleStart() {
    setLoading(true)
    onStart({ filter_mode: filterMode, max_products: maxProducts })
  }

  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-8">
          <span className="text-3xl">✦</span>
          <h1 className="mt-3 text-2xl font-semibold text-slate-900">BulkCopy AI</h1>
          <p className="mt-2 text-slate-500 text-sm leading-relaxed">
            Generates SEO-optimized, conversion-focused descriptions for your entire catalogue —
            written in <em>your brand's voice</em>, with predicted score improvements before you push.
          </p>
        </div>

        {/* Unique callouts */}
        <div className="grid grid-cols-3 gap-3 mb-8">
          {[
            { icon: '🧬', label: 'Brand Voice Fingerprinting', desc: 'Learns your style from existing products' },
            { icon: '📈', label: 'Score Preview', desc: 'See predicted score before pushing to Shopify' },
            { icon: '✅', label: 'Review & Push', desc: 'Approve, edit, reject — then push in one click' },
          ].map(f => (
            <div key={f.label} className="bg-slate-50 rounded-xl p-3 text-center border border-slate-100">
              <p className="text-xl mb-1">{f.icon}</p>
              <p className="text-[11px] font-semibold text-slate-700 leading-tight">{f.label}</p>
              <p className="text-[10px] text-slate-400 mt-0.5 leading-tight">{f.desc}</p>
            </div>
          ))}
        </div>

        {/* Config */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-5 shadow-sm">
          {/* Filter mode */}
          <div>
            <p className="text-xs font-semibold text-slate-700 mb-2">Which products to rewrite?</p>
            <div className="space-y-2">
              {[
                { value: 'low_score', label: 'Products needing the most help', desc: 'Prioritizes products with short or missing descriptions' },
                { value: 'all',       label: 'All products', desc: 'Process every active product in your store' },
              ].map(opt => (
                <label key={opt.value} className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${filterMode === opt.value ? 'border-brand-300 bg-brand-50' : 'border-slate-200 hover:bg-slate-50'}`}>
                  <input
                    type="radio"
                    name="filter"
                    value={opt.value}
                    checked={filterMode === opt.value}
                    onChange={() => setFilterMode(opt.value as 'low_score' | 'all')}
                    className="mt-0.5 accent-brand-600"
                  />
                  <div>
                    <p className="text-sm font-medium text-slate-800">{opt.label}</p>
                    <p className="text-xs text-slate-500">{opt.desc}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Max products */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <p className="text-xs font-semibold text-slate-700">Max products to generate</p>
              <span className="text-sm font-semibold text-brand-700">{maxProducts}</span>
            </div>
            <input
              type="range" min={5} max={100} step={5}
              value={maxProducts}
              onChange={e => setMaxProducts(Number(e.target.value))}
              className="w-full accent-brand-600"
            />
            <div className="flex justify-between text-[10px] text-slate-400 mt-1">
              <span>5</span><span>50</span><span>100</span>
            </div>
          </div>

          {/* Brand voice note */}
          <div className="flex items-start gap-2.5 px-3 py-2.5 bg-amber-50 border border-amber-100 rounded-xl">
            <span className="text-sm mt-0.5">🧬</span>
            <p className="text-[11px] text-amber-700 leading-relaxed">
              Brand voice is <strong>automatically detected</strong> from your existing product descriptions. No setup required — the AI learns your style before generating.
            </p>
          </div>

          <button
            onClick={handleStart}
            disabled={loading}
            className="w-full py-3 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold text-sm transition-colors flex items-center justify-center gap-2"
          >
            {loading ? <Spinner size={16} /> : <span>✦</span>}
            Generate Copy
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Generating view ───────────────────────────────────────────────────────────

function GeneratingView({
  session,
  sessionId,
  onCancelled,
}: {
  session: CopySession | null
  sessionId: string
  onCancelled: () => void
}) {
  const qc = useQueryClient()
  const requested = session?.products_requested ?? 0
  const generated = session?.products_generated ?? 0
  const pct = requested > 0 ? Math.round((generated / requested) * 100) : 0

  const cancel = useMutation({
    mutationFn: () => copyApi.cancel(sessionId),
    onSuccess: () => {
      qc.setQueryData(['copy', 'latest'], null)
      qc.removeQueries({ queryKey: ['copy', 'status', sessionId] })
      onCancelled()
    },
  })

  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center max-w-sm">
        <div className="w-16 h-16 rounded-full bg-brand-50 flex items-center justify-center mx-auto mb-5">
          <Spinner size={28} />
        </div>
        <h2 className="text-lg font-semibold text-slate-800 mb-1">Writing your copy...</h2>
        <p className="text-sm text-slate-500 mb-6">
          {generated > 0 ? (
            <>{generated} of {requested} products written</>
          ) : (
            'Analysing your brand voice — this takes a moment'
          )}
        </p>

        {/* Progress bar */}
        <div className="w-full bg-slate-100 rounded-full h-2 mb-3 overflow-hidden">
          <div
            className="h-2 bg-brand-500 rounded-full transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="text-xs text-slate-400">{pct}% complete</p>

        {session?.brand_voice && (
          <div className="mt-6 px-4 py-3 bg-amber-50 border border-amber-100 rounded-xl text-left">
            <p className="text-[10px] font-bold text-amber-600 uppercase tracking-widest mb-1">Brand Voice Detected</p>
            <p className="text-xs text-amber-800 italic">"{session.brand_voice.summary}"</p>
          </div>
        )}

        <button
          onClick={() => cancel.mutate()}
          disabled={cancel.isPending}
          className="mt-6 text-xs text-slate-400 hover:text-red-500 transition-colors flex items-center gap-1.5 mx-auto"
        >
          {cancel.isPending ? <Spinner size={12} /> : <span>✕</span>}
          Cancel and start over
        </button>
      </div>
    </div>
  )
}

// ── Review view ───────────────────────────────────────────────────────────────

function ReviewView({
  session,
  onNewSession,
}: {
  session: CopySession
  onNewSession: () => void
}) {
  const qc = useQueryClient()
  const results = session.results ?? []

  // Local selection + approval state (only sync to backend on edit/push)
  const [localStatus, setLocalStatus] = useState<Record<string, 'pending' | 'approved' | 'rejected'>>(() =>
    Object.fromEntries(
      results
        .filter(r => r.status !== 'pushed' && r.status !== 'failed')
        .map(r => [r.product_id, r.status === 'approved' ? 'approved' : r.status === 'rejected' ? 'rejected' : 'pending'])
    )
  )
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(results.filter(r => r.status !== 'rejected' && r.status !== 'pushed' && r.status !== 'failed').map(r => r.product_id))
  )
  const [pushResult, setPushResult] = useState<{ pushed: number; total: number } | null>(null)

  const push = useMutation({
    mutationFn: (ids: string[]) => copyApi.push(session._id, ids),
    onSuccess: (data) => {
      setPushResult({ pushed: data.pushed, total: data.total })
      qc.invalidateQueries({ queryKey: ['copy', 'results', session._id] })
    },
  })

  const pushedIds = new Set(results.filter(r => r.status === 'pushed' || r.status === 'failed').map(r => r.product_id))
  const nonRejectedSelected = [...selected].filter(id => localStatus[id] !== 'rejected' && !pushedIds.has(id))

  function toggleAll() {
    if (nonRejectedSelected.length === results.filter(r => localStatus[r.product_id] !== 'rejected' && r.status !== 'pushed').length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(results.filter(r => localStatus[r.product_id] !== 'rejected').map(r => r.product_id)))
    }
  }

  const avgDelta = results.reduce((acc, r) => {
    if (r.current_score !== null) acc.push(r.predicted_score - r.current_score)
    return acc
  }, [] as number[])
  const meanDelta = avgDelta.length > 0 ? Math.round(avgDelta.reduce((a, b) => a + b, 0) / avgDelta.length) : null

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-100 bg-white flex items-center justify-between flex-shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg">✦</span>
            <h1 className="text-base font-semibold text-slate-800">BulkCopy AI — Review</h1>
            {meanDelta !== null && meanDelta > 0 && (
              <span className="text-xs px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full font-semibold border border-emerald-200">
                avg +{meanDelta} score
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            {results.length} products generated
            {session.brand_voice && <> · Brand voice: <em>{session.brand_voice.tone}</em></>}
          </p>
        </div>
        <button
          onClick={onNewSession}
          className="text-xs px-3 py-1.5 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-lg font-medium"
        >
          New session
        </button>
      </div>

      {/* Push success banner */}
      {pushResult && (
        <div className="mx-6 mt-4 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between">
          <p className="text-sm text-emerald-800 font-medium">
            ✅ {pushResult.pushed}/{pushResult.total} products pushed to Shopify
          </p>
          <button onClick={() => setPushResult(null)} className="text-emerald-600 hover:text-emerald-800 text-xs">Dismiss</button>
        </div>
      )}

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 py-4">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="pb-2 px-4 w-10">
                <input
                  type="checkbox"
                  onChange={toggleAll}
                  checked={nonRejectedSelected.length > 0 && nonRejectedSelected.length === results.filter(r => localStatus[r.product_id] !== 'rejected' && r.status !== 'pushed').length}
                  className="w-4 h-4 rounded accent-brand-600 cursor-pointer"
                />
              </th>
              <th className="pb-2 px-3 w-12" />
              <th className="pb-2 px-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Product</th>
              <th className="pb-2 px-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wide w-32">Score</th>
              <th className="pb-2 px-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wide w-24">Status</th>
              <th className="pb-2 px-4 w-48" />
            </tr>
          </thead>
          <tbody>
            {results.map(product => (
              <ProductReviewRow
                key={product.product_id}
                product={product}
                sessionId={session._id}
                selected={selected.has(product.product_id)}
                localStatus={localStatus[product.product_id] ?? 'pending'}
                onToggleSelect={() => {
                  setSelected(prev => {
                    const next = new Set(prev)
                    next.has(product.product_id) ? next.delete(product.product_id) : next.add(product.product_id)
                    return next
                  })
                }}
                onStatusChange={(status) => {
                  setLocalStatus(prev => ({ ...prev, [product.product_id]: status }))
                  if (status === 'rejected') {
                    setSelected(prev => { const next = new Set(prev); next.delete(product.product_id); return next })
                  } else {
                    setSelected(prev => new Set([...prev, product.product_id]))
                  }
                }}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Sticky push bar */}
      <div className="flex-shrink-0 px-6 py-4 bg-white border-t border-slate-200 flex items-center justify-between">
        {nonRejectedSelected.length === 0 && pushedIds.size === results.length ? (
          <p className="text-sm text-emerald-600 font-medium flex items-center gap-1.5">
            <span>✓</span> All products pushed to Shopify
          </p>
        ) : (
          <p className="text-sm text-slate-500">
            <span className="font-semibold text-slate-800">{nonRejectedSelected.length}</span> product{nonRejectedSelected.length !== 1 ? 's' : ''} selected to push
          </p>
        )}
        <button
          onClick={() => push.mutate(nonRejectedSelected)}
          disabled={nonRejectedSelected.length === 0 || push.isPending}
          className="px-5 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold text-sm transition-colors flex items-center gap-2"
        >
          {push.isPending && <Spinner size={14} />}
          {nonRejectedSelected.length === 0 ? 'Nothing to push' : `Push ${nonRejectedSelected.length} to Shopify →`}
        </button>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function BulkCopyPage() {
  const qc = useQueryClient()
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)

  const { data: latestSession, isLoading: latestLoading } = useQuery({
    queryKey: ['copy', 'latest'],
    queryFn: copyApi.latest,
    staleTime: 5_000,
  })

  // Resolve which session to track
  const sessionId = activeSessionId ?? latestSession?._id ?? null
  const isGenerating = latestSession?.status === 'queued' || latestSession?.status === 'running'

  // Poll status while generating
  const { data: statusData } = useQuery({
    queryKey: ['copy', 'status', sessionId],
    queryFn: () => copyApi.status(sessionId!),
    enabled: !!sessionId && isGenerating,
    refetchInterval: 2_500,
  })

  // Fetch full results when complete
  const { data: resultsData } = useQuery({
    queryKey: ['copy', 'results', sessionId],
    queryFn: () => copyApi.results(sessionId!),
    enabled: !!sessionId && !isGenerating && latestSession?.status === 'complete',
    staleTime: 30_000,
  })

  // When status flips to complete, invalidate to load results
  useEffect(() => {
    if (statusData?.status === 'complete') {
      qc.invalidateQueries({ queryKey: ['copy', 'latest'] })
    }
  }, [statusData?.status, qc])

  const generate = useMutation({
    mutationFn: (cfg: { filter_mode: string; max_products: number }) =>
      copyApi.generate(cfg),
    onSuccess: (data) => {
      setActiveSessionId(data.data.session_id)
      qc.invalidateQueries({ queryKey: ['copy', 'latest'] })
    },
  })

  // ── Render ─────────────────────────────────────────────────────────────────

  if (latestLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Spinner size={28} />
      </div>
    )
  }

  // Show review if session complete and results loaded
  if (latestSession?.status === 'complete' && (resultsData || latestSession)) {
    const session = resultsData ?? latestSession
    return (
      <ReviewView
        session={session as CopySession}
        onNewSession={() => {
          setActiveSessionId(null)
          qc.removeQueries({ queryKey: ['copy', 'latest'] })
          qc.removeQueries({ queryKey: ['copy', 'results'] })
          // Optimistically clear so setup shows
          qc.setQueryData(['copy', 'latest'], null)
        }}
      />
    )
  }

  // Show generating progress
  if (isGenerating || latestSession?.status === 'queued') {
    const progressSession: CopySession = {
      ...(latestSession ?? {} as CopySession),
      products_requested: statusData?.products_requested ?? latestSession?.products_requested ?? 0,
      products_generated: statusData?.products_generated ?? latestSession?.products_generated ?? 0,
    }
    return (
      <GeneratingView
        session={progressSession}
        sessionId={sessionId!}
        onCancelled={() => setActiveSessionId(null)}
      />
    )
  }

  // Show setup
  return (
    <SetupCard
      onStart={(cfg) => generate.mutate(cfg)}
    />
  )
}
