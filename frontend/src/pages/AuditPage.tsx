import { useState } from 'react'
import { Link } from 'react-router-dom'
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
import { authApi, api } from '../lib/api'

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
  const { data: usageData } = useQuery({
    queryKey: ['billing-usage'],
    queryFn: () => api.get('/billing/usage').then(r => r.data),
    staleTime: 60_000,
  })
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null)

  const plan = me?.plan ?? 'free'
  const isFreePlan = plan === 'free' || plan === 'starter'
  const batchSize = usageData?.limits?.audit_batch_size ?? 0
  const totalProducts = usageData?.scan_state?.total_products ?? 0

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
          {(isTriggering || isRunning) ? (
            <Spinner size={14} className="text-white" />
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
          )}
          {isTriggering ? 'Starting…' : isRunning ? 'Running…' : 'Run new audit'}
        </button>
      </div>

      {/* Main content */}
      <div className="flex-1 px-8 py-6 space-y-5 max-w-6xl mx-auto w-full">
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

        {/* Free tier: batch scan info banner */}
        {isFreePlan && batchSize > 0 && !isRunning && activeAuditId && (
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl px-5 py-3 flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-sm text-blue-800 dark:text-blue-300">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <span>
                Free plan scans <strong>{batchSize} products per audit</strong>
                {totalProducts > 0 && ` (${totalProducts} total in your store)`}
                . Audits rotate through all products.
              </span>
            </div>
            <Link to="/plans" className="text-xs font-semibold text-blue-700 dark:text-blue-400 whitespace-nowrap hover:underline flex-shrink-0">
              Upgrade for full scans →
            </Link>
          </div>
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

        {/* Locked Pro features (shown to free users after first audit) */}
        {isFreePlan && isComplete && results && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <LockedFeatureCard
              icon="◈"
              title="Full audit history"
              description="Track score trends over time with charts showing every audit. See what improved and what regressed."
              plan="Pro"
            />
            <LockedFeatureCard
              icon="◎"
              title="Product filtering & sorting"
              description="Filter by severity, sort by score, and drill into every product detail with the full analysis drawer."
              plan="Pro"
            />
            <LockedFeatureCard
              icon="▤"
              title="Scheduled monitoring"
              description="Automatically audit your store weekly or daily. Get email alerts when products drop below your score threshold."
              plan="Pro"
            />
            <LockedFeatureCard
              icon="◻"
              title="Export reports"
              description="Download a full PDF or CSV report of your audit results to share with your team or clients."
              plan="Pro"
            />
          </div>
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

function LockedFeatureCard({
  icon,
  title,
  description,
  plan,
}: {
  icon: string
  title: string
  description: string
  plan: 'Pro' | 'Enterprise'
}) {
  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-5 py-4 relative overflow-hidden">
      <div className="absolute top-3 right-3">
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded
          ${plan === 'Enterprise'
            ? 'bg-purple-50 dark:bg-purple-900/40 text-purple-600 dark:text-purple-400'
            : 'bg-brand-50 dark:bg-brand-900/40 text-brand-600 dark:text-brand-400'
          }`}>
          {plan}
        </span>
      </div>
      <div className="flex items-start gap-3 mb-2 pr-12">
        <span className="text-lg text-slate-300 dark:text-slate-600 flex-shrink-0">{icon}</span>
        <div>
          <h3 className="text-sm font-semibold text-slate-400 dark:text-slate-500">{title}</h3>
          <p className="text-xs text-slate-400 dark:text-slate-600 mt-0.5 leading-relaxed">{description}</p>
        </div>
      </div>
      <Link
        to="/plans"
        className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline mt-1"
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
        Unlock with {plan}
      </Link>
    </div>
  )
}