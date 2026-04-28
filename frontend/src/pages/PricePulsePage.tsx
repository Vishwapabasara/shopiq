import { useActivePrice, usePriceResults, usePriceConfig } from '../hooks/usePrice'
import { PriceOverview } from '../components/price/PriceOverview'
import { PriceAlerts } from '../components/price/PriceAlerts'
import { PriceTable } from '../components/price/PriceTable'
import { EmptyState, Spinner } from '../components/ui'
import { formatDate, formatTime } from '../lib/utils'

export function PricePulsePage() {
  const {
    activeId,
    startAnalysis,
    cancelAnalysis,
    loadDemo,
    isCancelling,
    isTriggering,
    isLoadingDemo,
    triggerError,
    statusData,
    isRunning,
    isComplete,
    isFailed,
  } = useActivePrice()

  const { data: results, isLoading: resultsLoading } = usePriceResults(
    isComplete ? activeId : null
  )

  const { data: cfg } = usePriceConfig()
  const serpConfigured = cfg?.serpapi_configured ?? false

  const progressPct = statusData?.total_products
    ? Math.round((statusData.products_analyzed / statusData.total_products) * 100)
    : null

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      {/* Top bar */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 md:px-8 py-4 flex items-center justify-between lg:sticky top-0 z-10">
        <div>
          <h1 className="text-base font-semibold text-slate-900 dark:text-slate-100">PricePulse</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            {isComplete && results?.completed_at
              ? `Last checked ${formatDate(results.completed_at)} at ${formatTime(results.completed_at)}`
              : isRunning
              ? `Scanning market prices${progressPct !== null ? ` — ${progressPct}%` : '…'}`
              : 'Live competitor price monitoring — powered by Google Shopping'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {!serpConfigured && !isRunning && (
            <span className="text-[10px] font-medium bg-amber-50 text-amber-600 border border-amber-100 px-2 py-1 rounded-full">
              Add SERPAPI_KEY for live data
            </span>
          )}
          <button
            onClick={startAnalysis}
            disabled={isTriggering || isRunning || !serpConfigured}
            title={!serpConfigured ? 'Add SERPAPI_KEY environment variable to Railway to enable live scanning' : ''}
            className="btn-primary flex items-center gap-2 disabled:opacity-50"
          >
            {(isTriggering || isRunning) ? (
              <Spinner size={14} className="text-white" />
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>
                <line x1="7" y1="7" x2="7.01" y2="7"/>
              </svg>
            )}
            {isTriggering ? 'Starting…' : isRunning ? 'Scanning…' : 'Check prices'}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 px-4 md:px-8 py-6 space-y-5 max-w-6xl mx-auto w-full">

        {triggerError && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-sm text-red-700">
            Failed to start — {(triggerError as any)?.response?.data?.detail ?? 'please try again'}
          </div>
        )}

        {isRunning && (
          <div className="space-y-3">
            <div className="card px-6 py-8 flex flex-col items-center gap-4">
              <Spinner size={32} />
              <div className="text-center">
                <p className="text-sm font-medium text-slate-700">Scanning competitor prices…</p>
                <p className="text-xs text-slate-400 mt-1">
                  {statusData?.products_analyzed != null && statusData?.total_products
                    ? `Checked ${statusData.products_analyzed} of ${statusData.total_products} products via Google Shopping`
                    : 'Fetching your product catalogue and querying market prices'
                  }
                </p>
                {progressPct !== null && (
                  <div className="mt-3 w-48 h-1.5 bg-slate-100 rounded-full overflow-hidden mx-auto">
                    <div
                      className="h-full bg-brand-600 rounded-full transition-all duration-300"
                      style={{ width: `${progressPct}%` }}
                    />
                  </div>
                )}
              </div>
            </div>
            <div className="flex justify-center">
              <button
                onClick={cancelAnalysis}
                disabled={isCancelling}
                className="text-xs text-slate-400 hover:text-red-500 transition-colors underline underline-offset-2"
              >
                {isCancelling ? 'Cancelling…' : 'Cancel'}
              </button>
            </div>
          </div>
        )}

        {isFailed && !isRunning && (
          <div className="card px-6 py-5 border-red-200 bg-red-50">
            <p className="text-sm font-medium text-red-700 mb-1">Analysis failed</p>
            <p className="text-xs text-red-600">{statusData?.error_message}</p>
            {statusData?.error_message?.includes('SERPAPI_KEY') && (
              <p className="text-xs text-red-500 mt-2">
                Add <code className="bg-red-100 px-1 rounded">SERPAPI_KEY</code> to your Railway environment variables, then try again. Or use "Load demo data" to preview the feature.
              </p>
            )}
          </div>
        )}

        {!activeId && !isRunning && !isFailed && (
          <EmptyState
            icon="◉"
            title="See where you stand in the market"
            description="PricePulse searches Google Shopping for each of your products and compares live competitor prices — automatically, no manual setup. Know within minutes if you're being undercut or leaving money on the table."
            action={
              <div className="flex flex-col items-center gap-3">
                <div className="flex items-center gap-3 justify-center flex-wrap">
                  <button
                    onClick={startAnalysis}
                    disabled={isTriggering || isLoadingDemo || !serpConfigured}
                    className="btn-primary"
                    title={!serpConfigured ? 'SERPAPI_KEY required' : ''}
                  >
                    {isTriggering ? 'Starting…' : 'Check prices →'}
                  </button>
                  <button
                    onClick={loadDemo}
                    disabled={isTriggering || isLoadingDemo}
                    className="btn-secondary text-xs"
                  >
                    {isLoadingDemo ? 'Loading…' : 'Load demo data'}
                  </button>
                </div>
                {!serpConfigured && (
                  <p className="text-xs text-slate-400 max-w-sm text-center">
                    Live scanning requires a <strong>SERPAPI_KEY</strong> environment variable on Railway.
                    Use "Load demo data" to preview the feature without it.
                  </p>
                )}
              </div>
            }
          />
        )}

        {isComplete && resultsLoading && (
          <div className="flex justify-center py-16"><Spinner size={28} /></div>
        )}

        {isComplete && results && (
          <>
            <PriceOverview results={results} />
            <PriceAlerts products={results.products} currency={results.currency} />
            <PriceTable products={results.products} currency={results.currency} />
          </>
        )}
      </div>
    </div>
  )
}
