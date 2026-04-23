import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { priceApi, PriceAnalysisResults } from '../lib/api'

export function usePriceResults(analysisId: string | null) {
  return useQuery<PriceAnalysisResults>({
    queryKey: ['price-results', analysisId],
    queryFn: () => priceApi.results(analysisId!),
    enabled: !!analysisId,
    staleTime: 5 * 60_000,
  })
}

export function usePriceConfig() {
  return useQuery({
    queryKey: ['price-config'],
    queryFn: () => priceApi.config(),
    staleTime: 60_000,
  })
}

export function useActivePrice() {
  const qc = useQueryClient()

  const [activeId, setActiveId] = useState<string | null>(() =>
    localStorage.getItem('shopiq_active_price')
  )

  const _onSuccess = (res: any) => {
    const id = res.data.analysis_id
    setActiveId(id)
    localStorage.setItem('shopiq_active_price', id)
  }

  const cancel = useMutation({
    mutationFn: (id: string) => priceApi.cancel(id),
    onSuccess: () => {
      setActiveId(null)
      localStorage.removeItem('shopiq_active_price')
      qc.invalidateQueries({ queryKey: ['price-status'] })
    },
  })

  const trigger = useMutation({
    mutationFn: () => priceApi.analyze(),
    onSuccess: _onSuccess,
  })

  const seedDemo = useMutation({
    mutationFn: () => priceApi.seedDemo(),
    onSuccess: _onSuccess,
  })

  const statusQuery = useQuery({
    queryKey: ['price-status', activeId],
    queryFn: () => priceApi.status(activeId!),
    enabled: !!activeId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      if (s === 'complete' || s === 'failed') return false
      return 3000
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
    statusData,
    isRunning,
    isComplete,
    isFailed,
  }
}
