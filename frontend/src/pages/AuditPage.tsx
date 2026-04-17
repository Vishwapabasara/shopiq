import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useActiveAudit, useAuditResults } from '../hooks/useAudit'
import { ScoreOverview } from '../components/audit/ScoreOverview'
import { ProductTable } from '../components/audit/ProductTable'
import { ProductDrawer } from '../components/audit/ProductDrawer'
import { AuditProgress } from '../components/audit/AuditProgress'
import { ScoreHistory } from '../components/audit/ScoreHistory'
import { ScopeErrorModal } from '../components/audit/ScopeErrorModal'
import { UsageMeter } from '../components/UsageMeter'
import { UpgradeModal } from '../components/UpgradeModal'
import { EmptyState, Spinner } from '../components/ui'
import { formatDate, formatTime } from '../lib/utils'
import { authApi } from '../lib/api'

export function AuditPage() {
  const {
    activeAuditId,
    startAudit,
    isTriggering,
    triggerError,
    scopeError,
    clearScopeError,
    upgradeError,
    clearUpgradeError,
    statusData,
    isRunning,
  } = useActiveAudit()

  const { data: me } = useQuery({ queryKey: ['me'], queryFn: authApi.me })
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null)

  const isComplete = statusData?.status === 'complete'
  // ← removed local isRunning definition
  const isFailed   = statusData?.status === 'failed'

  const { data: results, isLoading: resultsLoading } = useAuditResults(
    isComplete ? activeAuditId : null
  )

  const reinstallUrl = me?.shop_domain
    ? `${import.meta.env.VITE_API_URL || 'https://shopiq-production.up.railway.app'}/auth/shopify/install?shop=${me.shop_domain}`
    : '#'

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      {/* Scope warning banner */}
      {me?.scope_issue && (me?.missing_scopes?.length ?? 0) > 0 && (
        <div className="bg-amber-50 border-b border-amber-200 px-8 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-amber-800">
            <span>⚠️</span>
            <span>
              ShopIQ is missing some permissions — audits may fail until you update them.
            </span>
          </div>
          <a
            href={reinstallUrl}
            className="text-sm font-medium text-amber-700 underline underline-offset-2 hover:text-amber-900 flex-shrink-0 ml-4"
          >
            Update permissions
          </a>
        </div>
      )}

      {/* Scope error modal */}
      {scopeError && me?.shop_domain && (
        <ScopeErrorModal
          missingScopes={scopeError.missing_scopes}
          shopDomain={me.shop_domain}
          onClose={clearScopeError}
        />
      )}

      {/* Upgrade modal */}
      {upgradeError && (
        <UpgradeModal
          reason={upgradeError.reason}
          message={upgradeError.message}
          onClose={clearUpgradeError}
        />
      )}

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
        <UsageMeter />

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

        {/* No audit yet — show empty state */}
        {!activeAuditId && !isRunning && !isFailed && (
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