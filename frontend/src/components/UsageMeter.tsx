import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

interface UsageData {
  plan: string
  limits: {
    audits_per_month: number
    copy_generations_per_month: number
    ai_fixes_per_month: number
    audit_batch_size: number
    history_audits: number
  }
  usage: {
    audits_used: number
    products_scanned: number
    copy_generations_used: number
    ai_fixes_used: number
    period_start: string | null
    period_end: string | null
  }
  scan_state: {
    total_products: number
    cursor: number
    scanned_product_ids: string[]
  }
}

function ProgressBar({ used, limit }: { used: number; limit: number }) {
  if (limit === -1 || limit === 0) {
    return (
      <div className="w-full bg-slate-100 dark:bg-slate-700 rounded-full h-1.5">
        <div className="h-1.5 rounded-full bg-emerald-400 w-full" />
      </div>
    )
  }
  const pct = Math.min((used / limit) * 100, 100)
  const color = pct >= 90 ? 'bg-red-400' : pct >= 70 ? 'bg-amber-400' : 'bg-emerald-400'
  return (
    <div className="w-full bg-slate-100 dark:bg-slate-700 rounded-full h-1.5">
      <div className={`h-1.5 rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

function UsageRow({ label, used, limit }: { label: string; used: number; limit: number }) {
  const display = limit === -1 ? '∞' : String(limit)
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400 mb-1">
        <span>{label}</span>
        <span>{used} / {display}</span>
      </div>
      <ProgressBar used={used} limit={limit} />
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

  const { plan, limits, usage, scan_state } = data
  const isFreePlan = plan === 'free' || plan === 'starter'
  const isScanBatched = limits.audit_batch_size > 0

  const auditsNearLimit = limits.audits_per_month !== -1 &&
    (usage.audits_used / limits.audits_per_month) >= 0.6
  const copyNearLimit = limits.copy_generations_per_month !== -1 &&
    limits.copy_generations_per_month > 0 &&
    (usage.copy_generations_used / limits.copy_generations_per_month) >= 0.6

  const showUpgrade = isFreePlan && (auditsNearLimit || copyNearLimit)

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-5 py-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
          Usage this month
        </span>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded capitalize
          ${plan === 'enterprise' ? 'bg-purple-50 dark:bg-purple-900/40 text-purple-600 dark:text-purple-400'
          : plan === 'pro' ? 'bg-brand-50 dark:bg-brand-900/40 text-brand-600 dark:text-brand-400'
          : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'}`}>
          {plan === 'starter' ? 'Free' : plan} plan
        </span>
      </div>

      <div className="space-y-3">
        <UsageRow
          label="Audits"
          used={usage.audits_used}
          limit={limits.audits_per_month}
        />
        {limits.copy_generations_per_month !== 0 && (
          <UsageRow
            label="AI copy generations"
            used={usage.copy_generations_used}
            limit={limits.copy_generations_per_month}
          />
        )}
        {limits.ai_fixes_per_month !== 0 && (
          <UsageRow
            label="AI fixes"
            used={usage.ai_fixes_used}
            limit={limits.ai_fixes_per_month}
          />
        )}
      </div>

      {/* Free tier: batch scan info */}
      {isFreePlan && isScanBatched && (
        <div className="mt-3 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
          <p className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-0.5">
            Rotating scan — {limits.audit_batch_size} products per audit
          </p>
          {scan_state.total_products > 0 ? (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {scan_state.total_products} total products &middot; batches rotate so every product is covered
            </p>
          ) : (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Run your first audit to begin scanning
            </p>
          )}
          <Link to="/plans" className="text-xs text-brand-600 dark:text-brand-400 font-medium mt-1 inline-block hover:underline">
            Upgrade for full scans →
          </Link>
        </div>
      )}

      {/* Upgrade CTA when approaching limits */}
      {showUpgrade && (
        <div className="mt-3 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
          <p className="text-xs text-yellow-800 dark:text-yellow-300 font-medium mb-1">
            Running low on free plan limits
          </p>
          <p className="text-xs text-yellow-700 dark:text-yellow-400 mb-2">
            Upgrade to Pro for 100 audits, full product scans, and 200 AI copy generations per month.
          </p>
          <Link
            to="/plans"
            className="inline-block bg-yellow-600 hover:bg-yellow-700 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition"
          >
            View Plans
          </Link>
        </div>
      )}
    </div>
  )
}
