import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reviewsApi, ReviewBatch, ReviewItem } from '../lib/api'
import { Spinner } from '../components/ui'

// ── Star rating ───────────────────────────────────────────────────────────────

function Stars({ rating }: { rating: number }) {
  return (
    <span className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map(i => (
        <span key={i} className={`text-sm ${i <= rating ? 'text-amber-400' : 'text-zinc-200'}`}>★</span>
      ))}
    </span>
  )
}

// ── Sentiment badge ───────────────────────────────────────────────────────────

const SENTIMENT_STYLE = {
  positive: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  neutral:  'bg-zinc-100 text-zinc-600',
  negative: 'bg-red-50 text-red-600 border border-red-200',
}

function SentimentBadge({ sentiment }: { sentiment: string | null }) {
  if (!sentiment) return null
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full capitalize ${SENTIMENT_STYLE[sentiment as keyof typeof SENTIMENT_STYLE] ?? SENTIMENT_STYLE.neutral}`}>
      {sentiment}
    </span>
  )
}

// ── Status badge ──────────────────────────────────────────────────────────────

const STATUS_STYLE: Record<string, string> = {
  pending:  'bg-zinc-100 text-zinc-500',
  approved: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  rejected: 'bg-red-50 text-red-500',
  posted:   'bg-brand-50 text-brand-700 border border-brand-200',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full capitalize ${STATUS_STYLE[status] ?? STATUS_STYLE.pending}`}>
      {status}
    </span>
  )
}

// ── Review card ───────────────────────────────────────────────────────────────

function ReviewCard({
  review,
  batchId,
  selected,
  localStatus,
  onToggleSelect,
  onStatusChange,
}: {
  review: ReviewItem
  batchId: string
  selected: boolean
  localStatus: 'pending' | 'approved' | 'rejected'
  onToggleSelect: () => void
  onStatusChange: (s: 'approved' | 'rejected') => void
}) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(review.edited_response ?? review.ai_response ?? '')

  const isPosted = review.status === 'posted'
  const displayStatus = isPosted ? 'posted' : localStatus
  const activeResponse = review.edited_response ?? review.ai_response ?? ''

  const saveEdit = useMutation({
    mutationFn: () => reviewsApi.editReview(batchId, review.review_id, editText),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reviews', 'results', batchId] })
      setEditing(false)
      onStatusChange('approved')
    },
  })

  return (
    <div className={`bg-white dark:bg-zinc-900 border rounded overflow-hidden transition-opacity ${localStatus === 'rejected' ? 'opacity-40' : 'border-zinc-200 dark:border-zinc-800'} ${review.is_escalation ? 'border-red-300 dark:border-red-800 ring-1 ring-red-200' : ''}`}>
      {/* Escalation banner */}
      {review.is_escalation && (
        <div className="px-4 py-2 bg-red-50 border-b border-red-200 flex items-center gap-2">
          <span className="text-red-500 text-sm">⚠</span>
          <p className="text-xs font-semibold text-red-600">Escalation — needs manager attention</p>
        </div>
      )}

      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* ── Left: Review ── */}
        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={selected}
              onChange={onToggleSelect}
              disabled={isPosted || localStatus === 'rejected'}
              className="mt-0.5 w-4 h-4 rounded accent-brand-600 cursor-pointer flex-shrink-0"
            />
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <Stars rating={review.rating} />
                <SentimentBadge sentiment={review.sentiment} />
                <StatusBadge status={displayStatus} />
              </div>
              <p className="text-xs font-semibold text-zinc-700 mt-1">{review.author}</p>
              <p className="text-[11px] text-zinc-400">{review.date}</p>
            </div>
          </div>

          {review.product_title && (
            <div className="flex items-center gap-2">
              {review.product_image && (
                <img src={review.product_image} alt="" className="w-6 h-6 rounded object-cover flex-shrink-0" />
              )}
              <span className="text-[11px] text-zinc-500 truncate">{review.product_title}</span>
            </div>
          )}

          {review.title && (
            <p className="text-sm font-medium text-zinc-800">"{review.title}"</p>
          )}
          <p className="text-sm text-zinc-600 leading-relaxed">{review.body}</p>
        </div>

        {/* ── Right: AI Response ── */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">AI Response</p>
            {!editing && !isPosted && (
              <button
                onClick={() => { setEditing(true); setEditText(activeResponse) }}
                className="text-[11px] text-brand-600 hover:text-brand-700 font-medium"
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
                rows={4}
                className="w-full border border-brand-300 rounded p-3 text-sm text-zinc-700 dark:text-zinc-300 dark:bg-zinc-800 focus:outline-none focus:ring-2 focus:ring-brand-200 resize-none"
              />
              <div className="flex gap-2 mt-2">
                <button
                  onClick={() => saveEdit.mutate()}
                  disabled={saveEdit.isPending}
                  className="text-xs px-3 py-1.5 bg-brand-200 text-brand-900 rounded hover:bg-brand-300 font-medium flex items-center gap-1"
                >
                  {saveEdit.isPending && <Spinner size={12} />}
                  Save & Approve
                </button>
                <button onClick={() => setEditing(false)} className="text-xs px-3 py-1.5 border border-zinc-200 dark:border-zinc-700 text-zinc-500 dark:text-zinc-400 rounded hover:bg-zinc-50 dark:hover:bg-zinc-800">
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className={`p-3.5 rounded text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed border ${review.edited_response ? 'border-brand-200 bg-brand-50/30 dark:bg-brand-200/5' : 'border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50'}`}>
              {activeResponse || <span className="italic text-zinc-300 dark:text-zinc-600">No response generated</span>}
              {review.edited_response && (
                <p className="text-[10px] text-brand-500 mt-1.5 font-medium">Edited</p>
              )}
            </div>
          )}

          {!editing && !isPosted && (
            <div className="flex gap-2">
              {localStatus !== 'approved' && (
                <button
                  onClick={() => onStatusChange('approved')}
                  className="text-[11px] px-3 py-1.5 rounded bg-emerald-50 text-emerald-700 hover:bg-emerald-100 font-medium transition-colors"
                >
                  Approve
                </button>
              )}
              {localStatus !== 'rejected' && (
                <button
                  onClick={() => onStatusChange('rejected')}
                  className="text-[11px] px-3 py-1.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-500 hover:bg-red-50 hover:text-red-600 font-medium transition-colors"
                >
                  Reject
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Generating view ───────────────────────────────────────────────────────────

function GeneratingView({ batch, batchId, onCancelled }: { batch: ReviewBatch | null; batchId: string; onCancelled: () => void }) {
  const qc = useQueryClient()
  const total = batch?.reviews_count ?? 0
  const done = batch?.responses_generated ?? 0
  const pct = total > 0 ? Math.round((done / total) * 100) : 0

  const cancel = useMutation({
    mutationFn: () => reviewsApi.cancel(batchId),
    onSuccess: () => {
      qc.setQueryData(['reviews', 'latest'], null)
      qc.removeQueries({ queryKey: ['reviews', 'status', batchId] })
      onCancelled()
    },
  })

  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center max-w-sm">
        <div className="w-16 h-16 rounded-full bg-brand-50 flex items-center justify-center mx-auto mb-5">
          <Spinner size={28} />
        </div>
        <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-100 mb-1">Writing your responses...</h2>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-6">
          {done > 0 ? <>{done} of {total} responses written</> : 'Detecting brand voice and analysing reviews...'}
        </p>
        <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2 mb-3 overflow-hidden">
          <div className="h-2 bg-brand-500 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
        </div>
        <p className="text-xs text-zinc-400">{pct}% complete</p>
        <button
          onClick={() => cancel.mutate()}
          disabled={cancel.isPending}
          className="mt-6 text-xs text-zinc-400 hover:text-red-500 transition-colors flex items-center gap-1.5 mx-auto"
        >
          {cancel.isPending ? <Spinner size={12} /> : <span>✕</span>}
          Cancel
        </button>
      </div>
    </div>
  )
}

// ── Empty / setup view ────────────────────────────────────────────────────────

function SetupView({ onSeedDemo }: { onSeedDemo: () => void }) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="w-full max-w-lg text-center">
        <span className="text-3xl">★</span>
        <h1 className="mt-3 text-2xl font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight">ReviewReply Pro</h1>
        <p className="mt-2 text-zinc-500 dark:text-zinc-400 text-sm leading-relaxed">
          AI-generated review responses written in your brand voice. Sentiment-aware, escalation-flagged, and ready to post in one click.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 my-8">
          {[
            { icon: '🎭', label: 'Sentiment-Aware', desc: 'Different tone for 5★ praise vs 1★ complaints' },
            { icon: '⚠️', label: 'Escalation Flags', desc: 'Auto-detects refund demands & legal threats' },
            { icon: '🧬', label: 'Brand Voice', desc: 'Reuses your BulkCopy AI brand fingerprint' },
          ].map(f => (
            <div key={f.label} className="bg-zinc-50 dark:bg-zinc-800/50 rounded p-3 text-center border border-zinc-100 dark:border-zinc-700">
              <p className="text-xl mb-1">{f.icon}</p>
              <p className="text-[11px] font-semibold text-zinc-700 leading-tight">{f.label}</p>
              <p className="text-[10px] text-zinc-400 mt-0.5 leading-tight">{f.desc}</p>
            </div>
          ))}
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg p-5 space-y-4">
          <button
            onClick={onSeedDemo}
            className="w-full py-3 bg-brand-200 hover:bg-brand-300 text-brand-900 rounded font-semibold text-sm transition-colors flex items-center justify-center gap-2"
          >
            <span>★</span> Load Demo Reviews & Generate Responses
          </button>
          <p className="text-[11px] text-zinc-400">
            Loads 8 realistic reviews with mixed ratings. Platform integrations (Google, Trustpilot) coming soon.
          </p>
        </div>
      </div>
    </div>
  )
}

// ── Review queue view ─────────────────────────────────────────────────────────

const FILTER_TABS = ['all', 'positive', 'neutral', 'negative', 'escalations'] as const
type FilterTab = typeof FILTER_TABS[number]

function ReviewQueueView({ batch, onReset }: { batch: ReviewBatch; onReset: () => void }) {
  const qc = useQueryClient()
  const reviews = batch.reviews ?? []
  const [activeTab, setActiveTab] = useState<FilterTab>('all')
  const [localStatus, setLocalStatus] = useState<Record<string, 'pending' | 'approved' | 'rejected'>>(() =>
    Object.fromEntries(
      reviews
        .filter(r => r.status !== 'posted')
        .map(r => [r.review_id, r.status === 'approved' ? 'approved' : r.status === 'rejected' ? 'rejected' : 'pending'])
    )
  )
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(reviews.filter(r => r.status !== 'posted' && r.status !== 'rejected').map(r => r.review_id))
  )
  const [postResult, setPostResult] = useState<{ posted: number; total: number } | null>(null)

  const postMutation = useMutation({
    mutationFn: (ids: string[]) => reviewsApi.post(batch._id, ids),
    onSuccess: (data) => {
      setPostResult({ posted: data.posted, total: data.total })
      qc.invalidateQueries({ queryKey: ['reviews', 'results', batch._id] })
    },
  })

  const filteredReviews = reviews.filter(r => {
    if (activeTab === 'all') return true
    if (activeTab === 'escalations') return r.is_escalation
    return r.sentiment === activeTab
  })

  const postedIds = new Set(reviews.filter(r => r.status === 'posted').map(r => r.review_id))
  const pendingToPost = [...selected].filter(id => localStatus[id] !== 'rejected' && !postedIds.has(id))

  const tabCounts: Record<FilterTab, number> = {
    all: reviews.length,
    positive: reviews.filter(r => r.sentiment === 'positive').length,
    neutral: reviews.filter(r => r.sentiment === 'neutral').length,
    negative: reviews.filter(r => r.sentiment === 'negative').length,
    escalations: reviews.filter(r => r.is_escalation).length,
  }

  const allPosted = reviews.length > 0 && reviews.every(r => r.status === 'posted')

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-between flex-shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg">★</span>
            <h1 className="text-base font-semibold text-zinc-800 dark:text-zinc-100 tracking-tight">ReviewReply Pro</h1>
          </div>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            {reviews.length} reviews · {reviews.filter(r => r.status === 'posted').length} posted
            {batch.brand_voice && <> · Voice: <em>{batch.brand_voice.tone}</em></>}
          </p>
        </div>
        <button
          onClick={onReset}
          className="text-xs px-3 py-1.5 border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800 rounded font-medium"
        >
          Reload
        </button>
      </div>

      {/* Filter tabs */}
      <div className="px-6 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex gap-1 flex-shrink-0">
        {FILTER_TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-2.5 text-xs font-medium capitalize border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === tab
                ? 'border-brand-600 text-brand-700 dark:text-brand-300'
                : 'border-transparent text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200'
            }`}
          >
            {tab === 'escalations' ? '⚠ ' : ''}
            {tab}
            {tabCounts[tab] > 0 && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${activeTab === tab ? 'bg-brand-100 dark:bg-brand-200/15 text-brand-700 dark:text-brand-300' : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400'}`}>
                {tabCounts[tab]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Post result banner */}
      {postResult && (
        <div className="mx-6 mt-4 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between flex-shrink-0">
          <p className="text-sm text-emerald-800 font-medium">✅ {postResult.posted}/{postResult.total} responses marked as posted</p>
          <button onClick={() => setPostResult(null)} className="text-emerald-600 hover:text-emerald-800 text-xs">Dismiss</button>
        </div>
      )}

      {/* Cards */}
      <div className="flex-1 overflow-auto px-6 py-4 space-y-3">
        {filteredReviews.length === 0 ? (
          <div className="text-center py-12 text-zinc-400 text-sm">No reviews in this category</div>
        ) : (
          filteredReviews.map(review => (
            <ReviewCard
              key={review.review_id}
              review={review}
              batchId={batch._id}
              selected={selected.has(review.review_id)}
              localStatus={localStatus[review.review_id] ?? 'pending'}
              onToggleSelect={() => {
                setSelected(prev => {
                  const next = new Set(prev)
                  next.has(review.review_id) ? next.delete(review.review_id) : next.add(review.review_id)
                  return next
                })
              }}
              onStatusChange={(status) => {
                setLocalStatus(prev => ({ ...prev, [review.review_id]: status }))
                if (status === 'rejected') {
                  setSelected(prev => { const next = new Set(prev); next.delete(review.review_id); return next })
                } else {
                  setSelected(prev => new Set([...prev, review.review_id]))
                }
              }}
            />
          ))
        )}
      </div>

      {/* Sticky post bar */}
      <div className="flex-shrink-0 px-6 py-4 bg-white dark:bg-zinc-900 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
        {allPosted ? (
          <p className="text-sm text-emerald-600 font-medium flex items-center gap-1.5">
            <span>✓</span> All responses posted
          </p>
        ) : (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            <span className="font-semibold text-zinc-800 dark:text-zinc-200">{pendingToPost.length}</span> response{pendingToPost.length !== 1 ? 's' : ''} selected
          </p>
        )}
        <button
          onClick={() => postMutation.mutate(pendingToPost)}
          disabled={pendingToPost.length === 0 || postMutation.isPending}
          className="px-5 py-2.5 bg-brand-200 hover:bg-brand-300 text-brand-900 disabled:opacity-50 disabled:cursor-not-allowed rounded font-semibold text-sm transition-colors flex items-center gap-2"
        >
          {postMutation.isPending && <Spinner size={14} />}
          {pendingToPost.length === 0 ? 'Nothing to post' : `Post ${pendingToPost.length} response${pendingToPost.length !== 1 ? 's' : ''} →`}
        </button>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function ReviewReplyPage() {
  const qc = useQueryClient()
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null)

  const { data: latestBatch, isLoading } = useQuery({
    queryKey: ['reviews', 'latest'],
    queryFn: reviewsApi.latest,
    staleTime: 5_000,
  })

  const batchId = activeBatchId ?? latestBatch?._id ?? null
  const isGenerating = latestBatch?.status === 'queued' || latestBatch?.status === 'running'

  const { data: statusData } = useQuery({
    queryKey: ['reviews', 'status', batchId],
    queryFn: () => reviewsApi.status(batchId!),
    enabled: !!batchId && isGenerating,
    refetchInterval: 2_500,
  })

  const { data: resultsData } = useQuery({
    queryKey: ['reviews', 'results', batchId],
    queryFn: () => reviewsApi.results(batchId!),
    enabled: !!batchId && !isGenerating && latestBatch?.status === 'complete',
    staleTime: 30_000,
  })

  useEffect(() => {
    if (statusData?.status === 'complete') {
      qc.invalidateQueries({ queryKey: ['reviews', 'latest'] })
    }
  }, [statusData?.status, qc])

  const seedDemo = useMutation({
    mutationFn: reviewsApi.seedDemo,
    onSuccess: (data) => {
      setActiveBatchId(data.batch_id)
      qc.invalidateQueries({ queryKey: ['reviews', 'latest'] })
    },
  })

  if (isLoading) {
    return <div className="flex-1 flex items-center justify-center"><Spinner size={28} /></div>
  }

  if (latestBatch?.status === 'complete' && (resultsData || latestBatch)) {
    const batch = resultsData ?? latestBatch
    return (
      <ReviewQueueView
        batch={batch as ReviewBatch}
        onReset={() => {
          setActiveBatchId(null)
          qc.setQueryData(['reviews', 'latest'], null)
        }}
      />
    )
  }

  if (isGenerating) {
    const progressBatch: ReviewBatch = {
      ...(latestBatch ?? {} as ReviewBatch),
      reviews_count: statusData?.reviews_count ?? latestBatch?.reviews_count ?? 0,
      responses_generated: statusData?.responses_generated ?? latestBatch?.responses_generated ?? 0,
    }
    return (
      <GeneratingView
        batch={progressBatch}
        batchId={batchId!}
        onCancelled={() => setActiveBatchId(null)}
      />
    )
  }

  return <SetupView onSeedDemo={() => seedDemo.mutate()} />
}
