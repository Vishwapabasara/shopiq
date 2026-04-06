import { useEffect, useState } from 'react'
import { Spinner, ProgressBar } from '../ui'
import type { AuditStatus } from '../../lib/api'

const STEPS = [
  { key: 'queued',   label: 'Queued',                     pct: 5  },
  { key: 'fetch',    label: 'Fetching products from Shopify', pct: 25 },
  { key: 'rules',    label: 'Running 18 audit rules',     pct: 55 },
  { key: 'ai',       label: 'GPT-4o scoring & rewrites',  pct: 85 },
  { key: 'complete', label: 'Finalising report',          pct: 100 },
]

interface Props {
  statusData: AuditStatus | undefined
}

export function AuditProgress({ statusData }: Props) {
  const [stepIdx, setStepIdx] = useState(0)

  // Auto-advance visual steps to give a sense of progress
  useEffect(() => {
    if (!statusData) return

    if (statusData.status === 'queued') { setStepIdx(0); return }
    if (statusData.status === 'failed') return
    if (statusData.status === 'complete') { setStepIdx(4); return }

    // While running, cycle through steps on a timer
    const timer = setInterval(() => {
      setStepIdx(prev => Math.min(prev + 1, 3))
    }, 8000)
    if (stepIdx === 0) setStepIdx(1)
    return () => clearInterval(timer)
  }, [statusData?.status])

  const current = STEPS[stepIdx]
  const isFailed = statusData?.status === 'failed'

  return (
    <div className="card p-8 max-w-lg mx-auto mt-16 text-center animate-fade-in">
      {isFailed ? (
        <>
          <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-4">
            <span className="text-red-500 text-xl">✕</span>
          </div>
          <h3 className="font-semibold text-slate-800 mb-2">Audit failed</h3>
          <p className="text-sm text-slate-500">{statusData?.error_message ?? 'An unexpected error occurred'}</p>
        </>
      ) : (
        <>
          <div className="flex justify-center mb-6">
            <div className="relative">
              <div className="w-16 h-16 rounded-full border-2 border-slate-100 flex items-center justify-center">
                <Spinner size={28} />
              </div>
            </div>
          </div>

          <h3 className="font-semibold text-slate-800 mb-1">Audit in progress</h3>
          <p className="text-sm text-slate-500 mb-6">{current.label}…</p>

          <ProgressBar value={current.pct} max={100} />

          <div className="mt-6 space-y-2">
            {STEPS.slice(0, 4).map((step, i) => (
              <div key={step.key} className="flex items-center gap-3 text-left">
                <div className={`w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center text-xs
                  ${i < stepIdx ? 'bg-emerald-100 text-emerald-600' :
                    i === stepIdx ? 'bg-brand-100 text-brand-600' :
                    'bg-slate-100 text-slate-300'}`}>
                  {i < stepIdx ? '✓' : i + 1}
                </div>
                <span className={`text-sm ${i <= stepIdx ? 'text-slate-700' : 'text-slate-400'}`}>
                  {step.label}
                </span>
                {i === stepIdx && <Spinner size={12} className="ml-auto" />}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
