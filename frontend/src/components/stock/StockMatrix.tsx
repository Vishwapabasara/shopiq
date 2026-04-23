import { StockAnalysisResults } from '../../lib/api'

interface Props {
  results: StockAnalysisResults
  selected: string | null
  onSelect: (status: string | null) => void
}

function fmt(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)
}

interface QuadrantProps {
  status: string
  label: string
  tagline: string
  count: number
  metric?: string
  metricLabel?: string
  colors: {
    bg: string
    border: string
    badge: string
    badgeText: string
    dot: string
    label: string
  }
  selected: boolean
  onClick: () => void
}

function Quadrant({ label, tagline, count, metric, metricLabel, colors, selected, onClick }: QuadrantProps) {
  return (
    <button
      onClick={onClick}
      className={`
        text-left p-4 rounded-xl border-2 transition-all duration-150
        ${colors.bg} ${selected ? colors.border + ' shadow-sm' : 'border-transparent'}
        hover:${colors.border} hover:shadow-sm
      `}
    >
      <div className="flex items-start justify-between mb-2">
        <span className={`text-xs font-semibold uppercase tracking-wide ${colors.label}`}>{label}</span>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${colors.badge} ${colors.badgeText}`}>
          {count} SKU{count !== 1 ? 's' : ''}
        </span>
      </div>
      <p className="text-xs text-slate-500 mb-3 leading-relaxed">{tagline}</p>
      {metric && (
        <div>
          <p className={`text-lg font-semibold tabular-nums ${colors.label}`}>{metric}</p>
          <p className="text-[10px] text-slate-400">{metricLabel}</p>
        </div>
      )}
    </button>
  )
}

export function StockMatrix({ results, selected, onSelect }: Props) {
  const rar = results.total_revenue_at_risk
  const dead = results.dead_stock_value

  const quadrants = [
    {
      status: 'urgent',
      label: 'Urgent Restock',
      tagline: 'Selling fast — stock running out. Act within days to protect revenue.',
      count: results.skus_urgent,
      metric: rar > 0 ? fmt(rar) : undefined,
      metricLabel: 'revenue at risk',
      colors: {
        bg: 'bg-red-50',
        border: 'border-red-300',
        badge: 'bg-red-100',
        badgeText: 'text-red-700',
        dot: 'bg-red-500',
        label: 'text-red-700',
      },
    },
    {
      status: 'healthy',
      label: 'Healthy Stock',
      tagline: 'Good velocity with adequate stock levels. Monitor for changes.',
      count: results.skus_healthy,
      metric: undefined,
      metricLabel: undefined,
      colors: {
        bg: 'bg-emerald-50',
        border: 'border-emerald-300',
        badge: 'bg-emerald-100',
        badgeText: 'text-emerald-700',
        dot: 'bg-emerald-500',
        label: 'text-emerald-700',
      },
    },
    {
      status: 'monitor',
      label: 'Monitor',
      tagline: 'Slower moving — will need restocking soon. Plan ahead.',
      count: results.skus_monitor,
      metric: undefined,
      metricLabel: undefined,
      colors: {
        bg: 'bg-blue-50',
        border: 'border-blue-300',
        badge: 'bg-blue-100',
        badgeText: 'text-blue-700',
        dot: 'bg-blue-400',
        label: 'text-blue-700',
      },
    },
    {
      status: 'dead_stock',
      label: 'Dead Stock',
      tagline: 'Little to no sales velocity. Capital locked — consider clearance.',
      count: results.skus_dead_stock,
      metric: dead > 0 ? fmt(dead) : undefined,
      metricLabel: 'capital locked',
      colors: {
        bg: 'bg-amber-50',
        border: 'border-amber-300',
        badge: 'bg-amber-100',
        badgeText: 'text-amber-700',
        dot: 'bg-amber-400',
        label: 'text-amber-700',
      },
    },
  ]

  return (
    <div className="card px-5 py-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-sm font-semibold text-slate-800">Inventory Health Matrix</p>
          <p className="text-xs text-slate-400 mt-0.5">Click a quadrant to filter the product table</p>
        </div>
        {selected && (
          <button
            onClick={() => onSelect(null)}
            className="text-xs text-slate-400 hover:text-slate-700 underline underline-offset-2 transition-colors"
          >
            Clear filter
          </button>
        )}
      </div>

      {/* Axis labels */}
      <div className="relative">
        <div className="absolute -left-4 top-1/2 -translate-y-1/2 -rotate-90 text-[9px] font-semibold text-slate-400 uppercase tracking-widest whitespace-nowrap">
          Demand velocity
        </div>
        <div className="pl-2">
          <div className="grid grid-cols-2 gap-3">
            {/* Row 1: urgent + healthy (high velocity) */}
            {quadrants.slice(0, 2).map(q => (
              <Quadrant
                key={q.status}
                {...q}
                selected={selected === q.status}
                onClick={() => onSelect(selected === q.status ? null : q.status)}
              />
            ))}
            {/* Row 2: monitor + dead_stock (low velocity) */}
            {quadrants.slice(2, 4).map(q => (
              <Quadrant
                key={q.status}
                {...q}
                selected={selected === q.status}
                onClick={() => onSelect(selected === q.status ? null : q.status)}
              />
            ))}
          </div>
          <div className="mt-2 text-center text-[9px] font-semibold text-slate-400 uppercase tracking-widest">
            Days of stock remaining →
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="mt-4 pt-4 border-t border-slate-100 flex flex-wrap gap-4">
        {quadrants.map(q => (
          <div key={q.status} className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${q.colors.dot}`} />
            <span className="text-xs text-slate-500">{q.label}</span>
            <span className="text-xs font-semibold text-slate-700">{q.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
