import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { stockApi, StockAnalysisResults } from '../lib/api'

export function useStockResults(analysisId: string | null) {
  return useQuery<StockAnalysisResults>({
    queryKey: ['stock-results', analysisId],
    queryFn: () => stockApi.results(analysisId!),
    enabled: !!analysisId,
    staleTime: 5 * 60_000,
  })
}

export function useActiveStock() {
  const qc = useQueryClient()

  const [activeId, setActiveId] = useState<string | null>(() =>
    localStorage.getItem('shopiq_active_stock')
  )
  const [upgradeError, setUpgradeError] = useState<{ reason: string; message: string } | null>(null)

  const cancel = useMutation({
    mutationFn: (id: string) => stockApi.cancel(id),
    onSuccess: () => {
      setActiveId(null)
      localStorage.removeItem('shopiq_active_stock')
      qc.invalidateQueries({ queryKey: ['stock-status'] })
    },
  })

  const _onSuccess = (res: any) => {
    const id = res.data.analysis_id
    setActiveId(id)
    localStorage.setItem('shopiq_active_stock', id)
  }

  const trigger = useMutation({
    mutationFn: () => stockApi.analyze(),
    onSuccess: _onSuccess,
    onError: (err: any) => {
      if (err?.response?.status === 402) {
        setUpgradeError({
          reason:  err.response.data?.reason  ?? 'limit_reached',
          message: err.response.data?.message ?? 'Upgrade to continue.',
        })
      }
    },
  })

  const seedDemo = useMutation({
    mutationFn: () => stockApi.seedDemo(),
    onSuccess: _onSuccess,
  })

  const statusQuery = useQuery({
    queryKey: ['stock-status', activeId],
    queryFn: () => stockApi.status(activeId!),
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
    startAnalysis:  () => trigger.mutate(),
    cancelAnalysis: () => activeId && cancel.mutate(activeId),
    loadDemo:       () => seedDemo.mutate(),
    isCancelling:   cancel.isPending,
    isTriggering:   trigger.isPending,
    isLoadingDemo:  seedDemo.isPending,
    triggerError:   trigger.error,
    upgradeError,
    clearUpgradeError: () => setUpgradeError(null),
    statusData,
    isRunning,
    isComplete,
    isFailed,
  }
}
