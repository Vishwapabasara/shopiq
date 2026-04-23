import { ReturnAnalysisResults } from '../../lib/api'

interface Props { results: ReturnAnalysisResults }

function StatCard({
  label, value, sub, accent = 'default',
}: { label: string; value: string; sub?: string; accent?: 'default' | 'red' | 'amber' | 'green' }) {
  const colors = {
    default: 'text-slate-900',
    red:     'text-red-600',
    amber:   'text-amber-600',
    green:   'text-emerald-600',
  }
  return (
    <div className="card px-5 py-4">
      <p className="text-xs text-slate-400 font-medium mb-1">{label}</p>
      <p className={`text-2xl font-bold ${colors[accent]}`}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  )
}

function RateRing({ rate }: { rate: number }) {
  const r = 44
  const circ = 2 * Math.PI * r
  const pct = Math.min(rate, 100)
  const dash = (pct / 100) * circ
  const color = rate < 10 ? '#10b981' : rate < 20 ? '#f59e0b' : '#ef4444'

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={108} height={108} viewBox="0 0 108 108">
        <circle cx={54} cy={54} r={r} fill="none" stroke="#f1f5f9" strokeWidth={10} />
        <circle
          cx={54} cy={54} r={r} fill="none"
          stroke={color} strokeWidth={10}
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeDashoffset={circ / 4}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.6s ease' }}
        />
        <text x={54} y={50} textAnchor="middle" fontSize={20} fontWeight="700" fill={color}>
          {rate}%
        </text>
        <text x={54} y={66} textAnchor="middle" fontSize={10} fill="#94a3b8">
          return rate
        </text>
      </svg>
      <p className="text-xs font-medium text-slate-500">
        {rate < 10 ? '✅ Excellent' : rate < 20 ? '⚠️ Average' : '❌ High'}
      </p>
    </div>
  )
}

export function ReturnOverview({ results }: Props) {
  const fmt = (n: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: results.currency, maximumFractionDigits: 0 }).format(n)

  return (
    <div className="space-y-4">
      {/* Insights */}
      {results.insights.length > 0 && (
        <div className="card px-5 py-4 space-y-2 border-brand-100 bg-brand-50">
          {results.insights.map((ins, i) => (
            <p key={i} className="text-sm text-brand-800 flex gap-2">
              <span className="text-brand-400 flex-shrink-0">•</span>
              {ins}
            </p>
          ))}
        </div>
      )}

      {/* Rate ring + stat cards */}
      <div className="card px-6 py-6">
        <div className="flex flex-col md:flex-row items-center gap-8">
          <RateRing rate={results.return_rate} />
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 flex-1 w-full">
            <StatCard
              label="Refunded orders"
              value={String(results.total_refunded)}
              sub={`of ${results.orders_analyzed} analysed`}
              accent={results.return_rate >= 20 ? 'red' : results.return_rate >= 10 ? 'amber' : 'green'}
            />
            <StatCard
              label="Refund value"
              value={fmt(results.total_refund_value)}
              sub="last 90 days"
              accent="default"
            />
            <StatCard
              label="Orders analysed"
              value={String(results.orders_analyzed)}
              sub="last 90 days"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
