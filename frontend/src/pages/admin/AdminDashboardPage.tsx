import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminApi, adminAuth, AdminStats, AdminTenant, AdminEvent } from '../../lib/adminApi'
import { cn } from '../../lib/utils'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number | null | undefined, fallback = '—') {
  if (n === null || n === undefined) return fallback
  return n.toLocaleString()
}

function fmtDate(iso: string | null | undefined) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function fmtDateTime(iso: string | null | undefined) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  })
}

function timeAgo(iso: string | null | undefined) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

const PLAN_BADGE: Record<string, string> = {
  free: 'bg-slate-100 text-slate-600',
  pro: 'bg-blue-100 text-blue-700',
  enterprise: 'bg-purple-100 text-purple-700',
}

const STATUS_BADGE: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  trial: 'bg-amber-100 text-amber-700',
  past_due: 'bg-red-100 text-red-700',
  cancelled: 'bg-slate-100 text-slate-500',
  frozen: 'bg-slate-100 text-slate-500',
}

const EVENT_STYLE: Record<string, { color: string; label: string }> = {
  plan_upgraded:       { color: 'text-emerald-600', label: 'Upgraded' },
  plan_downgraded:     { color: 'text-amber-600',   label: 'Downgraded' },
  downgrade_scheduled: { color: 'text-amber-500',   label: 'Downgrade scheduled' },
  downgrade_cancelled: { color: 'text-blue-600',    label: 'Downgrade cancelled' },
  subscription_cancelled: { color: 'text-red-500',  label: 'Cancelled' },
  subscription_renewed: { color: 'text-emerald-500', label: 'Renewed' },
  payment_declined:    { color: 'text-red-600',     label: 'Payment declined' },
  admin_override:      { color: 'text-purple-600',  label: 'Admin override' },
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, accent = 'default' }: {
  label: string; value: string | number; sub?: string
  accent?: 'green' | 'blue' | 'purple' | 'amber' | 'red' | 'default'
}) {
  const valueColor = {
    green: 'text-emerald-600', blue: 'text-blue-600',
    purple: 'text-purple-600', amber: 'text-amber-500',
    red: 'text-red-500', default: 'text-slate-900',
  }[accent]
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={cn('text-3xl font-bold tabular-nums', valueColor)}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  )
}

function Spinner() {
  return (
    <svg className="animate-spin w-5 h-5 text-brand-600" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.2" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

function Pagination({ page, pages, onChange }: { page: number; pages: number; onChange: (p: number) => void }) {
  if (pages <= 1) return null
  return (
    <div className="flex items-center gap-2 justify-end mt-4">
      <button
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 disabled:opacity-40 hover:bg-slate-50 transition-colors"
      >
        ← Prev
      </button>
      <span className="text-xs text-slate-500">Page {page} of {pages}</span>
      <button
        onClick={() => onChange(page + 1)}
        disabled={page >= pages}
        className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 disabled:opacity-40 hover:bg-slate-50 transition-colors"
      >
        Next →
      </button>
    </div>
  )
}

// ── Plan Override Modal ───────────────────────────────────────────────────────

function PlanOverrideModal({
  tenant,
  onConfirm,
  onClose,
}: {
  tenant: AdminTenant
  onConfirm: (plan: string) => Promise<void>
  onClose: () => void
}) {
  const [selected, setSelected] = useState(tenant.plan)
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    if (selected === tenant.plan) return onClose()
    setLoading(true)
    await onConfirm(selected)
    setLoading(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-sm p-6">
        <h3 className="text-base font-semibold text-slate-900 mb-1">Override Plan</h3>
        <p className="text-xs text-slate-500 mb-5 truncate">{tenant.shop_domain}</p>

        <div className="space-y-2 mb-6">
          {(['free', 'pro', 'enterprise'] as const).map(p => (
            <label key={p} className={cn(
              'flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors',
              selected === p
                ? 'border-brand-500 bg-brand-50'
                : 'border-slate-200 hover:bg-slate-50'
            )}>
              <input
                type="radio"
                name="plan"
                value={p}
                checked={selected === p}
                onChange={() => setSelected(p)}
                className="accent-brand-600"
              />
              <div>
                <p className="text-sm font-medium text-slate-800 capitalize">{p}</p>
                <p className="text-xs text-slate-400">
                  {p === 'free' ? 'Free forever' : p === 'pro' ? '$29/month' : '$199/month'}
                </p>
              </div>
              {tenant.plan === p && (
                <span className="ml-auto text-[10px] font-medium text-slate-400">current</span>
              )}
            </label>
          ))}
        </div>

        <div className="flex gap-3">
          <button
            onClick={onClose}
            disabled={loading}
            className="flex-1 py-2.5 px-4 border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={loading || selected === tenant.plan}
            className="flex-1 py-2.5 px-4 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white rounded-xl text-sm font-semibold transition-colors flex items-center justify-center gap-2"
          >
            {loading && <Spinner />}
            Apply
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'stores' | 'events'

// ── Overview Tab ──────────────────────────────────────────────────────────────

function OverviewTab({ stats, recentEvents }: { stats: AdminStats | null; recentEvents: AdminEvent[] }) {
  if (!stats) {
    return <div className="flex items-center justify-center py-20"><Spinner /></div>
  }

  return (
    <div className="space-y-6">
      {/* Stat grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Stores" value={fmt(stats.total_stores)} />
        <StatCard label="Monthly Revenue" value={`$${fmt(stats.mrr)}`} sub="MRR" accent="green" />
        <StatCard label="Active Trials" value={fmt(stats.active_trials)} accent="amber" />
        <StatCard label="Past Due" value={fmt(stats.past_due)} accent={stats.past_due > 0 ? 'red' : 'default'} />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Free Stores" value={fmt(stats.stores_by_plan.free)} />
        <StatCard label="Pro Stores" value={fmt(stats.stores_by_plan.pro)} accent="blue" />
        <StatCard label="Enterprise" value={fmt(stats.stores_by_plan.enterprise)} accent="purple" />
        <StatCard label="New This Month" value={fmt(stats.new_this_month)} accent="green" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <StatCard label="Audits This Month" value={fmt(stats.total_audits_this_month)} sub="across all stores" />
        <StatCard label="AI Copy Gens" value={fmt(stats.total_copy_this_month)} sub="this month" />
      </div>

      {/* Plan distribution bar */}
      <div className="bg-white border border-slate-200 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">Plan Distribution</h3>
        {stats.total_stores > 0 ? (
          <div className="space-y-3">
            {(['free', 'pro', 'enterprise'] as const).map(p => {
              const count = stats.stores_by_plan[p]
              const pct = Math.round((count / stats.total_stores) * 100)
              const barColor = p === 'enterprise' ? 'bg-purple-500' : p === 'pro' ? 'bg-blue-500' : 'bg-slate-300'
              return (
                <div key={p}>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs font-medium text-slate-600 capitalize">{p}</span>
                    <span className="text-xs text-slate-400 tabular-nums">{count} ({pct}%)</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className={cn('h-full rounded-full transition-all', barColor)} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-sm text-slate-400 text-center py-4">No stores yet</p>
        )}
      </div>

      {/* Recent events */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h3 className="text-sm font-semibold text-slate-700">Recent Activity</h3>
        </div>
        {recentEvents.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-10">No events yet</p>
        ) : (
          <div className="divide-y divide-slate-50">
            {recentEvents.slice(0, 8).map(e => {
              const style = EVENT_STYLE[e.event_type] ?? { color: 'text-slate-600', label: e.event_type }
              return (
                <div key={e.id} className="px-5 py-3 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-slate-700 truncate">
                      {e.shop_domain || e.tenant_id}
                    </p>
                    <p className={cn('text-xs', style.color)}>
                      {style.label}
                      {e.from_plan && e.to_plan && e.from_plan !== e.to_plan && (
                        <span className="text-slate-400"> · {e.from_plan} → {e.to_plan}</span>
                      )}
                    </p>
                  </div>
                  <span className="text-xs text-slate-400 flex-shrink-0">{timeAgo(e.created_at)}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Stores Tab ────────────────────────────────────────────────────────────────

function StoresTab() {
  const [tenants, setTenants] = useState<AdminTenant[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterPlan, setFilterPlan] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [overrideTenant, setOverrideTenant] = useState<AdminTenant | null>(null)
  const [successMsg, setSuccessMsg] = useState('')

  const load = useCallback(async (p = 1) => {
    setLoading(true)
    try {
      const res = await adminApi.tenants({ search, plan: filterPlan, status: filterStatus, page: p })
      setTenants(res.tenants)
      setTotal(res.total)
      setPage(res.page)
      setPages(res.pages)
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }, [search, filterPlan, filterStatus])

  useEffect(() => { load(1) }, [load])

  const handleOverride = async (plan: string) => {
    if (!overrideTenant) return
    await adminApi.overridePlan(overrideTenant.id, plan)
    setOverrideTenant(null)
    setSuccessMsg(`Plan updated to ${plan}`)
    setTimeout(() => setSuccessMsg(''), 3000)
    await load(page)
  }

  return (
    <div>
      {overrideTenant && (
        <PlanOverrideModal
          tenant={overrideTenant}
          onConfirm={handleOverride}
          onClose={() => setOverrideTenant(null)}
        />
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-5">
        <input
          type="text"
          placeholder="Search store…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="border border-slate-200 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 min-w-48"
        />
        <select
          value={filterPlan}
          onChange={e => setFilterPlan(e.target.value)}
          className="border border-slate-200 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">All plans</option>
          <option value="free">Free</option>
          <option value="pro">Pro</option>
          <option value="enterprise">Enterprise</option>
        </select>
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="border border-slate-200 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="trial">Trial</option>
          <option value="past_due">Past due</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <span className="text-xs text-slate-400 self-center ml-auto">{total} store{total !== 1 ? 's' : ''}</span>
      </div>

      {successMsg && (
        <div className="mb-4 bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm px-4 py-2.5 rounded-xl">
          {successMsg}
        </div>
      )}

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Store</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Plan</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Audits</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">AI Copy</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Last Active</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Installed</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {loading ? (
                <tr>
                  <td colSpan={8} className="text-center py-16">
                    <div className="flex justify-center"><Spinner /></div>
                  </td>
                </tr>
              ) : tenants.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-16 text-slate-400 text-sm">No stores found</td>
                </tr>
              ) : tenants.map(t => {
                const auditPct = t.usage.audits_limit === -1 ? 0
                  : Math.min(100, Math.round((t.usage.audits_used / Math.max(t.usage.audits_limit, 1)) * 100))
                const copyPct = t.usage.copy_limit === -1 ? 0
                  : Math.min(100, Math.round((t.usage.copy_used / Math.max(t.usage.copy_limit, 1)) * 100))

                return (
                  <tr key={t.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-900 text-xs truncate max-w-[180px]">
                        {t.shop_name || t.shop_domain}
                      </p>
                      <p className="text-[10px] text-slate-400 truncate max-w-[180px]">{t.shop_domain}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        'text-xs font-semibold px-2 py-0.5 rounded-full capitalize',
                        PLAN_BADGE[t.plan] ?? 'bg-slate-100 text-slate-600'
                      )}>
                        {t.plan}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        'text-xs font-medium px-2 py-0.5 rounded-full capitalize',
                        STATUS_BADGE[t.subscription_status] ?? 'bg-slate-100 text-slate-500'
                      )}>
                        {t.subscription_status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-xs text-slate-700 tabular-nums">
                        {t.usage.audits_used} / {t.usage.audits_limit === -1 ? '∞' : t.usage.audits_limit}
                      </p>
                      <div className="w-16 h-1 bg-slate-100 rounded-full mt-1">
                        <div
                          className={cn('h-full rounded-full', auditPct >= 90 ? 'bg-red-400' : auditPct >= 70 ? 'bg-amber-400' : 'bg-emerald-400')}
                          style={{ width: `${auditPct}%` }}
                        />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-xs text-slate-700 tabular-nums">
                        {t.usage.copy_used} / {t.usage.copy_limit === -1 ? '∞' : t.usage.copy_limit}
                      </p>
                      <div className="w-16 h-1 bg-slate-100 rounded-full mt-1">
                        <div
                          className={cn('h-full rounded-full', copyPct >= 90 ? 'bg-red-400' : copyPct >= 70 ? 'bg-amber-400' : 'bg-blue-400')}
                          style={{ width: `${copyPct}%` }}
                        />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">{timeAgo(t.usage.last_updated)}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{fmtDate(t.installed_at)}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => setOverrideTenant(t)}
                        className="text-xs font-medium text-brand-600 hover:text-brand-700 whitespace-nowrap"
                      >
                        Override plan
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <Pagination page={page} pages={pages} onChange={p => load(p)} />
    </div>
  )
}

// ── Events Tab ────────────────────────────────────────────────────────────────

function EventsTab() {
  const [events, setEvents] = useState<AdminEvent[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async (p = 1) => {
    setLoading(true)
    try {
      const res = await adminApi.events({ page: p })
      setEvents(res.events)
      setTotal(res.total)
      setPage(res.page)
      setPages(res.pages)
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(1) }, [load])

  return (
    <div>
      <p className="text-xs text-slate-400 mb-5">{total} total event{total !== 1 ? 's' : ''}</p>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Time</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Store</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Event</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Plan Change</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {loading ? (
                <tr>
                  <td colSpan={5} className="text-center py-16">
                    <div className="flex justify-center"><Spinner /></div>
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-16 text-slate-400 text-sm">No events yet</td>
                </tr>
              ) : events.map(e => {
                const style = EVENT_STYLE[e.event_type] ?? { color: 'text-slate-600', label: e.event_type }
                return (
                  <tr key={e.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{fmtDateTime(e.created_at)}</td>
                    <td className="px-4 py-3 text-xs text-slate-700 truncate max-w-[200px]">
                      {e.shop_domain || e.tenant_id}
                    </td>
                    <td className={cn('px-4 py-3 text-xs font-medium whitespace-nowrap', style.color)}>
                      {style.label}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600">
                      {e.from_plan && e.to_plan ? (
                        <span>
                          <span className="capitalize">{e.from_plan}</span>
                          <span className="text-slate-400 mx-1">→</span>
                          <span className="capitalize">{e.to_plan}</span>
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600 tabular-nums">
                      {e.amount > 0 ? `$${e.amount.toFixed(2)}` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <Pagination page={page} pages={pages} onChange={p => load(p)} />
    </div>
  )
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

export function AdminDashboardPage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('overview')
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [recentEvents, setRecentEvents] = useState<AdminEvent[]>([])

  useEffect(() => {
    adminApi.stats().then(setStats).catch(() => {})
    adminApi.events({ page: 1 }).then(r => setRecentEvents(r.events)).catch(() => {})
  }, [])

  const logout = () => {
    adminAuth.logout()
    navigate('/admin/login')
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'stores', label: 'Stores' },
    { key: 'events', label: 'Events' },
  ]

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top nav */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 md:px-6 h-14 flex items-center justify-between gap-2 overflow-x-auto">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 bg-brand-600 rounded-lg flex items-center justify-center flex-shrink-0">
              <span className="text-white text-xs font-bold">S</span>
            </div>
            <span className="font-semibold text-slate-900 text-sm">ShopIQ</span>
            <span className="text-slate-300 text-sm">·</span>
            <span className="text-xs font-medium text-slate-500">Admin</span>
          </div>

          {/* Tab nav */}
          <div className="flex items-center gap-1">
            {tabs.map(t => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={cn(
                  'px-4 py-1.5 rounded-lg text-sm font-medium transition-colors',
                  tab === t.key
                    ? 'bg-slate-100 text-slate-900'
                    : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                )}
              >
                {t.label}
                {t.key === 'stores' && stats && (
                  <span className="ml-1.5 text-[10px] bg-slate-200 text-slate-600 rounded-full px-1.5 py-0.5 font-semibold">
                    {stats.total_stores}
                  </span>
                )}
              </button>
            ))}
          </div>

          <button
            onClick={logout}
            className="text-xs font-medium text-slate-500 hover:text-slate-700 transition-colors"
          >
            Sign out
          </button>
        </div>
      </nav>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 md:px-6 py-6">
        {tab === 'overview' && <OverviewTab stats={stats} recentEvents={recentEvents} />}
        {tab === 'stores' && <StoresTab />}
        {tab === 'events' && <EventsTab />}
      </div>
    </div>
  )
}
