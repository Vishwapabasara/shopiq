import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { api } from '../lib/api'
import { Spinner } from '../components/ui'
import { cn } from '../lib/utils'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Achievement {
  id: string; title: string; description: string; icon: string; unlocked: boolean
}

interface Subscription {
  status: string
  trial_ends_at: string | null
  cancel_at_period_end: boolean
  shopify_charge_id: string | null
  current_period_end: string | null
  pending_downgrade_plan: string | null
  pending_downgrade_at: string | null
}

interface ProfileData {
  shop_name: string; shop_domain: string; shop_email: string; installed_at: string | null
  plan: string
  plan_config: {
    name: string; price: number; trial_days?: number
    audits_per_month: number; copy_generations_per_month: number
    ai_fixes_per_month: number; audit_batch_size: number; features: string[]
  }
  subscription: Subscription
  usage: { audits_used: number; copy_generations_used: number; ai_fixes_used: number; period_start: string | null }
  limits: { audits_per_month: number; copy_generations_per_month: number; ai_fixes_per_month: number }
  audit_stats: { total_completed: number; best_score: number | null; latest_score: number | null; first_score: number | null; score_improvement: number | null; total_copy_sessions: number }
  score_history: { created_at: string; overall_score: number }[]
  achievements: Achievement[]
  scan_state: { total_products: number; cursor: number }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreColor(s: number) {
  return s >= 75 ? 'text-emerald-600 dark:text-emerald-400' : s >= 50 ? 'text-amber-500' : 'text-red-500'
}

const PLAN_NAMES: Record<string, string> = { free: 'Free', pro: 'Pro', enterprise: 'Enterprise' }

function MiniScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const sw = 6
  const r = (size / 2) - sw - 2
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ
  const color = score >= 75 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444'
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90 absolute inset-0">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={sw} className="dark:stroke-slate-700" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={sw}
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.8s ease-out' }} />
      </svg>
      <span className={cn('text-xl font-bold tabular-nums z-10', scoreColor(score))}>{score}</span>
    </div>
  )
}

function UsageBar({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = limit === -1 ? 0 : Math.min((used / limit) * 100, 100)
  const color = pct >= 90 ? 'bg-red-400' : pct >= 70 ? 'bg-amber-400' : 'bg-emerald-400'
  const display = limit === -1 ? '∞' : String(limit)
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400 mb-1.5">
        <span className="font-medium">{label}</span>
        <span className="tabular-nums">{used} / {display}</span>
      </div>
      <div className="w-full bg-slate-100 dark:bg-slate-700 rounded-full h-2">
        <div className={cn('h-2 rounded-full transition-all', color)} style={{ width: limit === -1 ? '100%' : `${pct}%` }} />
      </div>
    </div>
  )
}

const PLAN_STYLE: Record<string, { badge: string; button: string }> = {
  free:       { badge: 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300', button: 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600' },
  pro:        { badge: 'bg-brand-50 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300', button: 'bg-brand-600 text-white hover:bg-brand-700' },
  enterprise: { badge: 'bg-purple-50 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300', button: 'bg-slate-900 dark:bg-purple-700 text-white hover:bg-slate-800 dark:hover:bg-purple-600' },
}

// ── Main component ────────────────────────────────────────────────────────────

export function AccountPage() {
  const qc = useQueryClient()
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null)
  const [planError, setPlanError] = useState<string | null>(null)

  const { data, isLoading } = useQuery<ProfileData>({
    queryKey: ['account-profile'],
    queryFn: () => api.get<ProfileData>('/account/profile').then(r => r.data),
    staleTime: 30_000,
  })

  const handlePlanChange = async (planKey: string) => {
    if (!data || planKey === data.plan || loadingPlan) return
    setLoadingPlan(planKey)
    setPlanError(null)
    try {
      const res = await api.post<{
        test_mode?: boolean; scheduled?: boolean
        confirmation_url?: string; message?: string
      }>(`/billing/subscribe/${planKey}`).then(r => r.data)

      if (res.confirmation_url) {
        window.top!.location.href = res.confirmation_url
        return
      }
      await qc.invalidateQueries({ queryKey: ['me'] })
      await qc.invalidateQueries({ queryKey: ['account-profile'] })
      await qc.invalidateQueries({ queryKey: ['billing-usage'] })
    } catch (err: any) {
      setPlanError(err?.response?.data?.detail ?? err?.message ?? 'Failed to change plan.')
    } finally {
      setLoadingPlan(null)
    }
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center py-32">
        <Spinner size={28} />
      </div>
    )
  }

  if (!data) return null

  const {
    shop_name, shop_domain, shop_email, installed_at,
    plan, plan_config, subscription,
    usage, limits,
    audit_stats, score_history, achievements, scan_state,
  } = data

  const chartData = score_history.map(h => ({
    date: new Date(h.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    score: h.overall_score,
  }))

  const installedDate = installed_at
    ? new Date(installed_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    : null

  const unlockedCount = achievements.filter(a => a.unlocked).length
  const planStyle = PLAN_STYLE[plan] ?? PLAN_STYLE.free

  const isTrialActive = subscription.status === 'trial' && !!subscription.trial_ends_at
  const isPastDue = subscription.status === 'past_due'

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-slate-50 dark:bg-slate-950">
      {/* Top bar */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 md:px-8 py-4 flex items-center justify-between lg:sticky top-0 z-10">
        <div>
          <h1 className="text-base font-semibold text-slate-900 dark:text-slate-100">Account</h1>
          <p className="text-xs text-slate-400 mt-0.5">{shop_domain}</p>
        </div>
        <span className={cn('text-xs font-semibold px-2.5 py-1 rounded-full capitalize', planStyle.badge)}>
          {plan_config.name} plan
        </span>
      </div>

      {/* Global banners */}
      {isPastDue && (
        <div className="bg-red-500 text-white text-xs font-medium px-4 md:px-8 py-2.5">
          Payment failed — your subscription is past due. Please contact support.
        </div>
      )}
      {isTrialActive && (
        <div className="bg-amber-500 text-white text-xs font-medium px-4 md:px-8 py-2.5">
          Trial active — expires {new Date(subscription.trial_ends_at!).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}.
        </div>
      )}

      <div className="flex-1 px-4 md:px-8 py-6 max-w-5xl mx-auto w-full space-y-6">

        {/* ── Row 1: Score progress + stats ───────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

          {/* Latest score card */}
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 flex flex-col items-center justify-center gap-3">
            {audit_stats.latest_score !== null ? (
              <>
                <MiniScoreRing score={audit_stats.latest_score} size={96} />
                <div className="text-center">
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Current Score</p>
                  {audit_stats.score_improvement !== null && (
                    <p className={cn(
                      'text-xs font-medium mt-0.5',
                      audit_stats.score_improvement > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500'
                    )}>
                      {audit_stats.score_improvement > 0 ? '▲' : '▼'} {Math.abs(audit_stats.score_improvement)} pts from first audit
                    </p>
                  )}
                </div>
              </>
            ) : (
              <div className="text-center">
                <p className="text-2xl mb-2 text-slate-300">◈</p>
                <p className="text-sm text-slate-500 dark:text-slate-400">No audits yet</p>
                <Link to="/dashboard" className="text-xs text-brand-600 dark:text-brand-400 font-medium mt-1 inline-block hover:underline">
                  Run your first audit →
                </Link>
              </div>
            )}
          </div>

          {/* Stat cards */}
          <div className="lg:col-span-2 grid grid-cols-2 sm:grid-cols-3 gap-4">
            <StatTile label="Total Audits" value={audit_stats.total_completed} icon="◈" />
            <StatTile label="Best Score" value={audit_stats.best_score ?? '—'} icon="★" accent="green" />
            <StatTile label="AI Copy Sessions" value={audit_stats.total_copy_sessions} icon="◻" accent="blue" />
            <StatTile label="Products Indexed" value={scan_state.total_products || '—'} icon="▣" />
            <StatTile
              label="Achievements"
              value={`${unlockedCount}/${achievements.length}`}
              icon="✦"
              accent={unlockedCount === achievements.length ? 'green' : 'default'}
            />
            <StatTile
              label="Member Since"
              value={installedDate ? new Date(installed_at!).toLocaleDateString('en-US', { month: 'short', year: 'numeric' }) : '—'}
              icon="◉"
            />
          </div>
        </div>

        {/* ── Score history chart ──────────────────────────────────────────────── */}
        {chartData.length >= 2 && (
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">Store Score Over Time</h2>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" className="dark:stroke-slate-700" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    fontSize: 12,
                    border: '1px solid #e2e8f0',
                    borderRadius: 8,
                    boxShadow: 'none',
                    backgroundColor: '#fff',
                  }}
                />
                <Line
                  type="monotone" dataKey="score" stroke="#2563eb"
                  strokeWidth={2.5} dot={{ r: 4, fill: '#2563eb', strokeWidth: 0 }}
                  activeDot={{ r: 5 }} name="Store Score"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* ── Row 3: Achievements ──────────────────────────────────────────────── */}
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Achievements</h2>
            <span className="text-xs text-slate-400 dark:text-slate-500">{unlockedCount} / {achievements.length} unlocked</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {achievements.map(a => (
              <div
                key={a.id}
                className={cn(
                  'rounded-xl p-3 border text-center transition-all',
                  a.unlocked
                    ? 'bg-brand-50 dark:bg-brand-900/30 border-brand-100 dark:border-brand-800'
                    : 'bg-slate-50 dark:bg-slate-700/30 border-slate-100 dark:border-slate-700 opacity-50'
                )}
              >
                <div className={cn('text-2xl mb-1.5', a.unlocked ? 'grayscale-0' : 'grayscale')}>
                  {a.icon}
                </div>
                <p className={cn('text-xs font-semibold leading-tight', a.unlocked ? 'text-slate-700 dark:text-slate-200' : 'text-slate-400 dark:text-slate-500')}>
                  {a.title}
                </p>
                <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5 leading-tight">
                  {a.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Row 4: Usage this month ──────────────────────────────────────────── */}
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Usage This Month</h2>
            {usage.period_start && (
              <span className="text-xs text-slate-400 dark:text-slate-500">
                Resets {new Date(new Date(usage.period_start).getFullYear(), new Date(usage.period_start).getMonth() + 1, 1).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </span>
            )}
          </div>
          <div className="space-y-4">
            <UsageBar label="Audits" used={usage.audits_used} limit={limits.audits_per_month} />
            {limits.copy_generations_per_month !== 0 && (
              <UsageBar label="AI Copy Generations" used={usage.copy_generations_used} limit={limits.copy_generations_per_month} />
            )}
            {limits.ai_fixes_per_month !== 0 && (
              <UsageBar label="AI Fixes" used={usage.ai_fixes_used} limit={limits.ai_fixes_per_month} />
            )}
          </div>
        </div>

        {/* ── Row 5: Plan management ───────────────────────────────────────────── */}
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">Your Plan</h2>

          {/* Current plan summary */}
          <div className={cn(
            'rounded-xl p-4 mb-5 border',
            plan === 'enterprise'
              ? 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800'
              : plan === 'pro'
              ? 'bg-brand-50 dark:bg-brand-900/20 border-brand-200 dark:border-brand-800'
              : 'bg-slate-50 dark:bg-slate-700/40 border-slate-200 dark:border-slate-700'
          )}>
            <div className="flex items-center justify-between mb-2">
              <div>
                <span className={cn('text-sm font-bold', planStyle.badge.split(' ').slice(2).join(' '))}>
                  {plan_config.name} Plan
                </span>
                <span className="text-xs text-slate-500 dark:text-slate-400 ml-2">
                  {plan_config.price === 0 ? 'Free forever' : `$${plan_config.price}/month`}
                </span>
              </div>
              {isTrialActive && (
                <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30 px-2 py-0.5 rounded-full">
                  Trial ends {new Date(subscription.trial_ends_at!).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </span>
              )}
            </div>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1">
              {plan_config.features.map((f, i) => (
                <li key={i} className="flex items-start gap-1.5 text-xs text-slate-600 dark:text-slate-300">
                  <span className="text-emerald-500 mt-0.5 flex-shrink-0">✓</span>
                  {f}
                </li>
              ))}
            </ul>
          </div>

          {planError && (
            <div className="mb-3 text-xs text-red-500 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-3 py-2">
              {planError}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {(['free', 'pro', 'enterprise'] as const).map(pk => {
              const isCurrent = pk === plan
              const ps = PLAN_STYLE[pk]
              const isLoading = loadingPlan === pk
              return (
                <button
                  key={pk}
                  onClick={() => handlePlanChange(pk)}
                  disabled={!!loadingPlan || isCurrent}
                  className={cn(
                    'w-full py-3 px-4 rounded-xl text-sm font-semibold border transition-all relative flex flex-col items-center gap-0.5',
                    isCurrent
                      ? 'border-transparent ring-2 ring-brand-500 cursor-default ' + ps.badge
                      : 'border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:border-brand-400 dark:hover:border-brand-600 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50'
                  )}
                >
                  {isLoading && (
                    <span className="absolute inset-0 flex items-center justify-center">
                      <Spinner size={16} />
                    </span>
                  )}
                  <span className={cn('font-semibold', isLoading && 'opacity-0')}>{PLAN_NAMES[pk]}</span>
                  <span className={cn('text-xs opacity-70', isLoading && 'opacity-0')}>
                    {pk === 'free' ? 'Free' : pk === 'pro' ? '$29/mo' : '$199/mo'}
                  </span>
                  {isCurrent && <span className="text-[10px] opacity-60">Current</span>}
                </button>
              )
            })}
          </div>

          {plan !== 'free' && subscription.shopify_charge_id && (
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-3">
              Billing is managed through Shopify. To cancel, select the Free plan above.
            </p>
          )}
        </div>

        {/* ── Row 6: Account info ──────────────────────────────────────────────── */}
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">Account Info</h2>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <InfoRow label="Store name" value={shop_name} />
            <InfoRow label="Shop domain" value={shop_domain} />
            {shop_email && <InfoRow label="Email" value={shop_email} />}
            {installedDate && <InfoRow label="Member since" value={installedDate} />}
          </dl>
        </div>

      </div>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatTile({
  label, value, icon, accent = 'default',
}: {
  label: string; value: string | number; icon: string; accent?: 'green' | 'blue' | 'default'
}) {
  const valueColor = accent === 'green'
    ? 'text-emerald-600 dark:text-emerald-400'
    : accent === 'blue'
    ? 'text-brand-600 dark:text-brand-400'
    : 'text-slate-900 dark:text-slate-100'

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-slate-300 dark:text-slate-600 text-base">{icon}</span>
        <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">{label}</p>
      </div>
      <p className={cn('text-2xl font-bold tabular-nums', valueColor)}>{value}</p>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-400 dark:text-slate-500 uppercase tracking-wide mb-0.5">{label}</dt>
      <dd className="text-sm text-slate-700 dark:text-slate-200 font-medium">{value}</dd>
    </div>
  )
}
