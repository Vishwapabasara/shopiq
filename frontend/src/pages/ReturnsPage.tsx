import { useActiveReturn, useReturnResults } from '../hooks/useReturns'
import { ReturnOverview } from '../components/returns/ReturnOverview'
import { ReturnCharts } from '../components/returns/ReturnCharts'
import { ReturnProgress } from '../components/returns/ReturnProgress'
import { ProductReturnTable } from '../components/returns/ProductReturnTable'
import { FlaggedCustomers } from '../components/returns/FlaggedCustomers'
import { EmptyState, Spinner } from '../components/ui'
import { UpgradeModal } from '../components/UpgradeModal'
import { formatDate, formatTime } from '../lib/utils'

export function ReturnsPage() {
  const {
    activeId,
    startAnalysis,
    cancelAnalysis,
    loadDemo,
    isCancelling,
    isTriggering,
    isLoadingDemo,
    triggerError,
    upgradeError,
    clearUpgradeError,
    statusData,
    isRunning,
    isComplete,
    isFailed,
  } = useActiveReturn()

  const { data: results, isLoading: resultsLoading } = useReturnResults(
    isComplete ? activeId : null
  )

  return (
    <div className="flex-1 flex flex-col min-h-screen">
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
          <h1 className="text-base font-semibold text-slate-900">ReturnRadar</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            {isComplete && results?.completed_at
              ? `Last analysed ${formatDate(results.completed_at)} at ${formatTime(results.completed_at)}`
              : isRunning
              ? 'Analysing orders…'
              : 'Return rate analytics and fraud detection'}
          </p>
        </div>

        <button
          onClick={startAnalysis}
          disabled={isTriggering || isRunning}
          className="btn-primary flex items-center gap-2"
        >
          {(isTriggering || isRunning) ? (
            <Spinner size={14} className="text-white" />
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="1 4 1 10 7 10"/>
              <path d="M3.51 15a9 9 0 1 0 .49-3.01"/>
            </svg>
          )}
          {isTriggering ? 'Starting…' : isRunning ? 'Analysing…' : 'Analyse returns'}
        </button>
      </div>

      {/* Main content */}
      <div className="flex-1 px-8 py-6 space-y-5 max-w-6xl mx-auto w-full">

        {/* Error */}
        {triggerError && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-sm text-red-700">
            Failed to start analysis — {(triggerError as any)?.response?.data?.detail ?? 'please try again'}
          </div>
        )}

        {/* Running */}
        {isRunning && (
          <div className="space-y-3">
            <ReturnProgress ordersAnalyzed={statusData?.orders_analyzed ?? 0} />
            <div className="flex justify-center">
              <button
                onClick={cancelAnalysis}
                disabled={isCancelling}
                className="text-xs text-slate-400 hover:text-red-500 transition-colors underline underline-offset-2"
              >
                {isCancelling ? 'Cancelling…' : 'Cancel analysis'}
              </button>
            </div>
          </div>
        )}

        {/* Failed */}
        {isFailed && !isRunning && (
          <div className="card px-6 py-5 border-red-200 bg-red-50">
            <p className="text-sm font-medium text-red-700 mb-1">Analysis failed</p>
            <p className="text-xs text-red-600">{statusData?.error_message}</p>
          </div>
        )}

        {/* Empty state */}
        {!activeId && !isRunning && !isFailed && (
          <EmptyState
            icon="↩"
            title="Analyse your returns"
            description="ReturnRadar scans 90 days of order history to calculate return rates by product, identify repeat returners, and surface actionable insights to reduce refunds."
            action={
              <div className="flex items-center gap-3 justify-center flex-wrap">
                <button onClick={startAnalysis} disabled={isTriggering || isLoadingDemo} className="btn-primary">
                  {isTriggering ? 'Starting…' : 'Start analysis →'}
                </button>
                <button
                  onClick={loadDemo}
                  disabled={isTriggering || isLoadingDemo}
                  className="btn-secondary text-xs"
                >
                  {isLoadingDemo ? 'Loading…' : 'Load demo data'}
                </button>
              </div>
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
            <ReturnOverview results={results} />
            <ReturnCharts results={results} />
            <ProductReturnTable
              products={results.top_returned_products}
              currency={results.currency}
            />
            <FlaggedCustomers customers={results.flagged_customers} />
          </>
        )}
      </div>
    </div>
  )
}
