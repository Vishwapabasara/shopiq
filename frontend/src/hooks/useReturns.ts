import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { returnsApi, ReturnAnalysisResults } from '../lib/api'

export function useReturnResults(analysisId: string | null) {
  return useQuery<ReturnAnalysisResults>({
    queryKey: ['return-results', analysisId],
    queryFn: () => returnsApi.results(analysisId!),
    enabled: !!analysisId,
    staleTime: 5 * 60_000,
  })
}

export function useActiveReturn() {
  const qc = useQueryClient()

  const [activeId, setActiveId] = useState<string | null>(() =>
    localStorage.getItem('shopiq_active_return')
  )
  const [upgradeError, setUpgradeError] = useState<{ reason: string; message: string } | null>(null)

  const trigger = useMutation({
    mutationFn: () => returnsApi.analyze(),
    onSuccess: (res) => {
      const id = res.data.analysis_id
      setActiveId(id)
      localStorage.setItem('shopiq_active_return', id)
      qc.invalidateQueries({ queryKey: ['return-history'] })
    },
    onError: (err: any) => {
      if (err?.response?.status === 402) {
        setUpgradeError({
          reason:  err.response.data?.reason  ?? 'limit_reached',
          message: err.response.data?.message ?? 'Upgrade to continue.',
        })
      }
    },
  })

  const statusQuery = useQuery({
    queryKey: ['return-status', activeId],
    queryFn: () => returnsApi.status(activeId!),
    enabled: !!activeId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      if (s === 'complete' || s === 'failed') return false
      return 2000
    },
  })

  const statusData = statusQuery.data
  const isRunning = statusData?.status === 'queued' || statusData?.status === 'running'
  const isComplete = statusData?.status === 'complete'
  const isFailed   = statusData?.status === 'failed'

  return {
    activeId,
    startAnalysis: () => trigger.mutate(),
    isTriggering: trigger.isPending,
    triggerError: trigger.error,
    upgradeError,
    clearUpgradeError: () => setUpgradeError(null),
    statusData,
    isRunning,
    isComplete,
    isFailed,
  }
}
