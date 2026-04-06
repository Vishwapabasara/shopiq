import { useState } from 'react'
import { useActiveAudit, useAuditResults } from '../hooks/useAudit'
import { ScoreOverview } from '../components/audit/ScoreOverview'
import { ProductTable } from '../components/audit/ProductTable'
import { ProductDrawer } from '../components/audit/ProductDrawer'
import { AuditProgress } from '../components/audit/AuditProgress'
import { ScoreHistory } from '../components/audit/ScoreHistory'
import { EmptyState, Spinner } from '../components/ui'
import { formatDate, formatTime } from '../lib/utils'

export function AuditPage() {
  const {
    activeAuditId,
    startAudit,
    isTriggering,
    triggerError,
    statusData,
  } = useActiveAudit()

  const [selectedProductId, setSelectedProductId] = useState<string | null>(null)

  const isComplete = statusData?.status === 'complete'
  const isRunning  = statusData?.status === 'queued' || statusData?.status === 'running'
  const isFailed   = statusData?.status === 'failed'

  const { data: results, isLoading: resultsLoading } = useAuditResults(
    isComplete ? activeAuditId : null
  )

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      {/* Top bar */}
      <div className="bg-white border-b border-slate-200 px-8 py-4 flex items-center justify-between sticky top-0 z-10">
        <div>
          <h1 className="text-base font-semibold text-slate-900">ShopAudit AI</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            {isComplete && statusData?.completed_at
              ? `Last audited ${formatDate(statusData.completed_at)} at ${formatTime(statusData.completed_at)}`
              : isRunning
              ? 'Audit in progress…'
              : 'Analyse every product in your store'}
          </p>
        </div>

        <button
          onClick={startAudit}
          disabled={isTriggering || isRunning}
          className="btn-primary flex items-center gap-2"
        >
          {(isTriggering || isRunning) && <Spinner size={14} className="text-white" />}
          {isTriggering ? 'Starting…' : isRunning ? 'Running…' : 'Run new audit'}
        </button>
      </div>

      {/* Main content */}
      <div className="flex-1 px-8 py-6 space-y-5 max-w-6xl">

        {/* Error state */}
        {triggerError && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-sm text-red-700">
            Failed to start audit — {(triggerError as any)?.response?.data?.detail ?? 'please try again'}
          </div>
        )}

        {/* Running state */}
        {isRunning && <AuditProgress statusData={statusData} />}

        {/* Failed state */}
        {isFailed && !isRunning && (
          <div className="card px-6 py-5 border-red-200 bg-red-50">
            <p className="text-sm font-medium text-red-700 mb-1">Last audit failed</p>
            <p className="text-xs text-red-600">{statusData?.error_message}</p>
          </div>
        )}

        {/* No audit yet */}
        {!activeAuditId && !isRunning && (
          <EmptyState
            icon="◈"
            title="Run your first audit"
            description="ShopAudit AI scans every product in your store — checking 18 SEO, content, UX, and catalogue rules, then uses GPT-4o to score and rewrite your descriptions."
            action={
              <button onClick={startAudit} disabled={isTriggering} className="btn-primary">
                {isTriggering ? 'Starting…' : 'Start audit →'}
              </button>
            }
          />
        )}

        {/* Loading results */}
        {isComplete && resultsLoading && (
          <div className="flex justify-center py-16"><Spinner size={28} /></div>
        )}

        {/* Results */}
        {isComplete && results && (
          <>
            <ScoreOverview results={results} />
            <ScoreHistory />
            <ProductTable
              auditId={activeAuditId!}
              onSelectProduct={setSelectedProductId}
            />
          </>
        )}
      </div>

      {/* Product detail drawer */}
      <ProductDrawer
        auditId={activeAuditId ?? ''}
        productId={selectedProductId}
        onClose={() => setSelectedProductId(null)}
      />
    </div>
  )
}
