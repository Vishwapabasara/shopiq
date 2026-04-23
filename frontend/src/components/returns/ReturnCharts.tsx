import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { ReturnAnalysisResults } from '../../lib/api'

const REASON_LABELS: Record<string, string> = {
  size_fit:   'Size / Fit',
  wrong_item: 'Wrong item',
  damaged:    'Damaged',
  quality:    'Quality',
  not_needed: 'Changed mind',
  fraud:      'Suspected fraud',
  exchange:   'Exchange',
  other:      'Other',
}

const REASON_COLORS: Record<string, string> = {
  size_fit:   '#6366f1',
  wrong_item: '#f59e0b',
  damaged:    '#ef4444',
  quality:    '#ec4899',
  not_needed: '#64748b',
  fraud:      '#dc2626',
  exchange:   '#10b981',
  other:      '#94a3b8',
}

interface Props { results: ReturnAnalysisResults }

export function ReturnCharts({ results }: Props) {
  const totalReasons = Object.values(results.reason_breakdown).reduce((a, b) => a + b, 0) || 1
  const reasons = Object.entries(results.reason_breakdown)
    .sort(([, a], [, b]) => b - a)

  const trendData = results.monthly_trend.map(m => ({
    month: m.month.slice(5),   // "2024-03" → "03"
    rate:  m.return_rate,
    label: new Date(m.month + '-01').toLocaleString('default', { month: 'short' }),
  }))

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Reason breakdown */}
      <div className="card px-5 py-5">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">
          Return reasons
        </p>
        {reasons.length === 0 ? (
          <p className="text-sm text-slate-400">No return reasons recorded.</p>
        ) : (
          <div className="space-y-3">
            {reasons.map(([key, count]) => {
              const pct = Math.round(count / totalReasons * 100)
              return (
                <div key={key}>
                  <div className="flex justify-between text-xs text-slate-500 mb-1">
                    <span>{REASON_LABELS[key] ?? key}</span>
                    <span className="font-medium text-slate-700">{count} ({pct}%)</span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full transition-all"
                      style={{ width: `${pct}%`, backgroundColor: REASON_COLORS[key] ?? '#94a3b8' }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Monthly trend */}
      <div className="card px-5 py-5">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">
          Return rate trend
        </p>
        {trendData.length < 2 ? (
          <p className="text-sm text-slate-400">Not enough data for a trend chart yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={trendData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} unit="%" />
              <Tooltip
                formatter={(v: number) => [`${v}%`, 'Return rate']}
                contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
              />
              <Line
                type="monotone" dataKey="rate" stroke="#6366f1" strokeWidth={2}
                dot={{ r: 3, fill: '#6366f1' }} activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
