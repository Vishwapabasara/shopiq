import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from 'recharts'
import { useAuditHistory } from '../../hooks/useAudit'
import { formatDate } from '../../lib/utils'

export function ScoreHistory() {
  const { data } = useAuditHistory()
  const history = [...(data?.history ?? [])].reverse()  // oldest first

  if (history.length < 2) return null

  const chartData = history.map(h => ({
    date: formatDate(h.created_at),
    overall: h.overall_score,
    seo: h.category_scores?.seo ?? 0,
    content: h.category_scores?.content ?? 0,
  }))

  return (
    <div className="card p-5">
      <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-4">Score history</h3>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#71717a' }} tickLine={false} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#71717a' }} tickLine={false} />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              border: '1px solid #27272a',
              borderRadius: 4,
              boxShadow: 'none',
              backgroundColor: '#18181b',
              color: '#e4e4e7',
            }}
          />
          <Line
            type="monotone" dataKey="overall" stroke="#dfd1ff"
            strokeWidth={2} dot={{ r: 3, fill: '#dfd1ff' }} name="Overall"
          />
          <Line
            type="monotone" dataKey="seo" stroke="#f59e0b"
            strokeWidth={1.5} dot={false} name="SEO" strokeDasharray="4 2"
          />
          <Line
            type="monotone" dataKey="content" stroke="#10b981"
            strokeWidth={1.5} dot={false} name="Content" strokeDasharray="4 2"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
