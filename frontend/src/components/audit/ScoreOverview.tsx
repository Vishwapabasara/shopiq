import { ScoreRing, CategoryBar, StatCard } from '../ui'
import { scoreLabel, categoryLabel, formatDate } from '../../lib/utils'
import type { AuditResults } from '../../lib/api'

const CATEGORY_WEIGHTS: Record<string, string> = {
  seo: '25%',
  content: '35%',
  ux: '25%',
  catalogue: '15%',
}

interface Props {
  results: AuditResults
}

export function ScoreOverview({ results }: Props) {
  const { overall_score, category_scores, products_scanned,
          critical_count, warning_count, info_count, completed_at } = results

  return (
    <div className="space-y-4">
      {/* Top row — overall score + stats */}
      <div className="card p-6">
        <div className="flex flex-col md:flex-row gap-8 items-center md:items-start">
          {/* Score ring */}
          <div className="flex flex-col items-center gap-2 flex-shrink-0">
            <ScoreRing score={overall_score} size={140} strokeWidth={10} />
            <span className="text-sm font-medium text-slate-600">{scoreLabel(overall_score)}</span>
            {completed_at && (
              <span className="text-xs text-slate-400">Audited {formatDate(completed_at)}</span>
            )}
          </div>

          {/* Category bars */}
          <div className="flex-1 w-full space-y-4 pt-1">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">
              Score by category
            </h2>
            {Object.entries(category_scores).map(([cat, score]) => (
              <CategoryBar
                key={cat}
                label={categoryLabel(cat)}
                score={score}
                weight={CATEGORY_WEIGHTS[cat] ?? ''}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Issue counts */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="Products scanned"
          value={products_scanned}
          sub="active products"
          accent="default"
        />
        <StatCard
          label="Critical issues"
          value={critical_count}
          sub="blocking conversion"
          accent="red"
        />
        <StatCard
          label="Warnings"
          value={warning_count}
          sub="hurting rankings"
          accent="amber"
        />
        <StatCard
          label="Info"
          value={info_count}
          sub="optimisation tips"
          accent="blue"
        />
      </div>
    </div>
  )
}
