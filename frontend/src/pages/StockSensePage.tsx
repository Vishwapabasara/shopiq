import { useState } from 'react'
import { useActiveStock, useStockResults } from '../hooks/useStock'
import { StockOverview } from '../components/stock/StockOverview'
import { StockMatrix } from '../components/stock/StockMatrix'
import { StockTable } from '../components/stock/StockTable'
import { ReorderPanel } from '../components/stock/ReorderPanel'
import { EmptyState, Spinner } from '../components/ui'
import { UpgradeModal } from '../components/UpgradeModal'
import { formatDate, formatTime } from '../lib/utils'

export function StockSensePage() {
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
  } = useActiveStock()

  const { data: results, isLoading: resultsLoading } = useStockResults(
    isComplete ? activeId : null
  )

  const [matrixFilter, setMatrixFilter] = useState<string | null>(null)

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      {upgradeError && (
        <UpgradeModal
          reason={upgradeError.reason}
          message={upgradeError.message}
          onClose={clearUpgradeError}
        />
      )}

      {/* Top bar */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 md:px-8 py-4 flex items-center justify-between lg:sticky top-0 z-10">
        <div>
          <h1 className="text-base font-semibold text-slate-900 dark:text-slate-100">StockSense</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            {isComplete && results?.completed_at
              ? `Last analysed ${formatDate(results.completed_at)} at ${formatTime(results.completed_at)}`
              : isRunning
              ? 'Scanning inventory…'
              : 'Inventory intelligence — velocity, risk & reorder signals'}
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
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
            </svg>
          )}
          {isTriggering ? 'Starting…' : isRunning ? 'Scanning…' : 'Analyse inventory'}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 px-4 md:px-8 py-6 space-y-5 max-w-6xl mx-auto w-full">

        {triggerError && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-sm text-red-700">
            Failed to start analysis — {(triggerError as any)?.response?.data?.detail ?? 'please try again'}
          </div>
        )}

        {isRunning && (
          <div className="space-y-3">
            <div className="card px-6 py-8 flex flex-col items-center gap-4">
              <Spinner size={32} />
              <div className="text-center">
                <p className="text-sm font-medium text-slate-700">Scanning your inventory…</p>
                <p className="text-xs text-slate-400 mt-1">
                  {statusData?.total_skus
                    ? `${statusData.total_skus} SKUs found so far`
                    : 'Fetching products and 60-day order history'
                  }
                </p>
              </div>
            </div>
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

        {isFailed && !isRunning && (
          <div className="card px-6 py-5 border-red-200 bg-red-50">
            <p className="text-sm font-medium text-red-700 mb-1">Analysis failed</p>
            <p className="text-xs text-red-600">{statusData?.error_message}</p>
          </div>
        )}

        {!activeId && !isRunning && !isFailed && (
          <EmptyState
            icon="⬡"
            title="Understand your inventory health"
            description="StockSense scans 60 days of velocity data to surface revenue at risk, dead stock capital, and precise reorder quantities — so you never run out of your best sellers or tie up cash in slow movers."
            action={
              <div className="flex items-center gap-3 justify-center flex-wrap">
                <button onClick={startAnalysis} disabled={isTriggering || isLoadingDemo} className="btn-primary">
                  {isTriggering ? 'Starting…' : 'Analyse inventory →'}
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

        {isComplete && resultsLoading && (
          <div className="flex justify-center py-16"><Spinner size={28} /></div>
        )}

        {isComplete && results && (
          <>
            <StockOverview results={results} />
            <StockMatrix
              results={results}
              selected={matrixFilter}
              onSelect={setMatrixFilter}
            />
            <ReorderPanel products={results.products} currency={results.currency} />
            <StockTable
              products={results.products}
              currency={results.currency}
              filterStatus={matrixFilter}
            />
          </>
        )}
      </div>
    </div>
  )
}
