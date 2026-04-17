import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

interface UsageData {
  plan: string
  limits: { audits_per_month: number; max_products: number }
  usage: { audits_used: number; products_scanned: number }
}

function ProgressBar({ used, limit }: { used: number; limit: number }) {
  if (limit === -1) {
    return (
      <div className="w-full bg-slate-100 rounded-full h-1.5">
        <div className="h-1.5 rounded-full bg-emerald-400 w-full" />
      </div>
    )
  }
  const pct = Math.min((used / limit) * 100, 100)
  const color = pct >= 90 ? 'bg-red-400' : pct >= 70 ? 'bg-amber-400' : 'bg-emerald-400'
  return (
    <div className="w-full bg-slate-100 rounded-full h-1.5">
      <div className={`h-1.5 rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

export function UsageMeter() {
  const { data } = useQuery<UsageData>({
    queryKey: ['billing-usage'],
    queryFn: () => api.get<UsageData>('/billing/usage').then(r => r.data),
    staleTime: 60_000,
  })

  if (!data) return null

  const { plan, limits, usage } = data
  const auditPct = limits.audits_per_month === -1
    ? 0
    : (usage.audits_used / limits.audits_per_month) * 100
  const showUpgradePrompt = plan === 'free' && auditPct >= 80

  return (
    <div className="bg-white border border-slate-200 rounded-xl px-5 py-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          Usage this month
        </span>
        <span className="text-xs font-medium text-brand-600 capitalize">{plan} plan</span>
      </div>

      <div className="space-y-3">
        <div>
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>Audits</span>
            <span>
              {usage.audits_used} / {limits.audits_per_month === -1 ? '∞' : limits.audits_per_month}
            </span>
          </div>
          <ProgressBar used={usage.audits_used} limit={limits.audits_per_month} />
        </div>

        <div>
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>Products scanned</span>
            <span>
              {usage.products_scanned} / {limits.max_products === -1 ? '∞' : limits.max_products}
            </span>
          </div>
          <ProgressBar used={usage.products_scanned} limit={limits.max_products} />
        </div>
      </div>

      {showUpgradePrompt && (
        <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between">
          <p className="text-xs text-slate-500">Running low on free audits</p>
          <Link
            to="/plans"
            className="text-xs font-semibold text-brand-600 hover:text-brand-700"
          >
            Upgrade →
          </Link>
        </div>
      )}
    </div>
  )
}
