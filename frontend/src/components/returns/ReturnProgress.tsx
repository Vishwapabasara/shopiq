import { Spinner } from '../ui'

interface Props {
  ordersAnalyzed: number
}

export function ReturnProgress({ ordersAnalyzed }: Props) {
  return (
    <div className="card px-6 py-8 flex flex-col items-center gap-4">
      <Spinner size={32} className="text-brand-600" />
      <div className="text-center">
        <p className="text-sm font-semibold text-slate-700">Analysing your orders…</p>
        {ordersAnalyzed > 0 && (
          <p className="text-xs text-slate-400 mt-1">{ordersAnalyzed} orders processed so far</p>
        )}
      </div>
      <div className="w-64 bg-slate-100 rounded-full h-1.5 overflow-hidden">
        <div className="h-1.5 rounded-full bg-brand-500 animate-pulse w-2/3" />
      </div>
      <p className="text-xs text-slate-400">Fetching 90 days of order history from Shopify</p>
    </div>
  )
}
