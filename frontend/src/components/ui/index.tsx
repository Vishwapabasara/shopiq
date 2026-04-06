import { cn, scoreColor, ringOffset } from '../../lib/utils'

// ── Score Ring ────────────────────────────────────────────────────────────────

interface ScoreRingProps {
  score: number
  size?: number
  strokeWidth?: number
  label?: string
  sublabel?: string
}

export function ScoreRing({
  score, size = 120, strokeWidth = 8, label, sublabel
}: ScoreRingProps) {
  const r = (size / 2) - strokeWidth - 2
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ
  const color = score >= 75 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444'

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="#e2e8f0" strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={color} strokeWidth={strokeWidth}
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.8s ease-out' }}
        />
      </svg>
      <div className="flex flex-col items-center -mt-[calc(50%+1rem)] mb-[calc(50%+1rem)] pointer-events-none">
        <span className={cn('text-3xl font-semibold tabular-nums', scoreColor(score))}>
          {score}
        </span>
        <span className="text-xs text-slate-400 font-medium">/100</span>
      </div>
      {label && <p className="text-sm font-medium text-slate-700">{label}</p>}
      {sublabel && <p className="text-xs text-slate-400">{sublabel}</p>}
    </div>
  )
}

// ── Stat Card ─────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  accent?: 'red' | 'amber' | 'green' | 'blue' | 'default'
}

const accentMap = {
  red: 'text-red-600',
  amber: 'text-amber-500',
  green: 'text-emerald-600',
  blue: 'text-blue-600',
  default: 'text-slate-900',
}

export function StatCard({ label, value, sub, accent = 'default' }: StatCardProps) {
  return (
    <div className="card p-4">
      <p className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1">{label}</p>
      <p className={cn('text-3xl font-semibold tabular-nums', accentMap[accent])}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  )
}

// ── Category Score Bar ────────────────────────────────────────────────────────

interface CategoryBarProps {
  label: string
  score: number
  weight: string
}

export function CategoryBar({ label, score, weight }: CategoryBarProps) {
  const color = score >= 75 ? 'bg-emerald-500' : score >= 50 ? 'bg-amber-400' : 'bg-red-400'
  return (
    <div>
      <div className="flex justify-between items-center mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700">{label}</span>
          <span className="text-xs text-slate-400">{weight}</span>
        </div>
        <span className={cn('text-sm font-semibold tabular-nums', scoreColor(score))}>{score}</span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-700', color)}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  )
}

// ── Severity Badge ────────────────────────────────────────────────────────────

export function SeverityBadge({ severity }: { severity: string }) {
  const cls = {
    critical: 'badge-critical',
    warning: 'badge-warning',
    info: 'badge-info',
  }[severity] ?? 'badge-info'
  return <span className={cls}>{severity}</span>
}

// ── Spinner ───────────────────────────────────────────────────────────────────

export function Spinner({ size = 20, className }: { size?: number; className?: string }) {
  return (
    <svg
      className={cn('animate-spin text-brand-600', className)}
      width={size} height={size} viewBox="0 0 24 24" fill="none"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.2" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

// ── Empty State ───────────────────────────────────────────────────────────────

interface EmptyStateProps {
  icon?: string
  title: string
  description: string
  action?: React.ReactNode
}

export function EmptyState({ icon = '🔍', title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="text-4xl mb-4">{icon}</div>
      <h3 className="text-base font-semibold text-slate-700 mb-2">{title}</h3>
      <p className="text-sm text-slate-500 max-w-sm mb-6">{description}</p>
      {action}
    </div>
  )
}

// ── Progress Bar ──────────────────────────────────────────────────────────────

export function ProgressBar({ value, max, label }: { value: number; max: number; label?: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="w-full">
      {label && (
        <div className="flex justify-between text-xs text-slate-500 mb-1">
          <span>{label}</span>
          <span>{pct}%</span>
        </div>
      )}
      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-brand-600 rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
