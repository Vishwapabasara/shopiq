import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { auditApi, type AuditResults } from '../lib/api'

// ── Trigger a new audit ───────────────────────────────────────────────────────

export function useTriggerAudit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => auditApi.run().then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['audit-history'] })
    },
  })
}

// ── Poll audit status until complete ─────────────────────────────────────────

export function useAuditStatus(auditId: string | null) {
  return useQuery({
    queryKey: ['audit-status', auditId],
    queryFn: () => auditApi.status(auditId!),
    enabled: !!auditId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'complete' || status === 'failed') return false
      return 2000   // poll every 2 seconds while running
    },
  })
}

// ── Full results ──────────────────────────────────────────────────────────────

export function useAuditResults(
  auditId: string | null,
  params?: { severity?: string; sort?: string; limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: ['audit-results', auditId, params],
    queryFn: () => auditApi.results(auditId!, params),
    enabled: !!auditId,
    staleTime: 60_000,
  })
}

// ── Product detail ────────────────────────────────────────────────────────────

export function useProductDetail(auditId: string | null, productId: string | null) {
  return useQuery({
    queryKey: ['product-detail', auditId, productId],
    queryFn: () => auditApi.productDetail(auditId!, productId!),
    enabled: !!auditId && !!productId,
    staleTime: 120_000,
  })
}

// ── Audit history ─────────────────────────────────────────────────────────────

export function useAuditHistory() {
  return useQuery({
    queryKey: ['audit-history'],
    queryFn: () => auditApi.history(),
    staleTime: 60_000,
  })
}

// ── Composed hook: manage active audit flow ───────────────────────────────────

export function useActiveAudit() {
  const [activeAuditId, setActiveAuditId] = useState<string | null>(() =>
    localStorage.getItem('shopiq_active_audit')
  )

  const trigger = useTriggerAudit()
  const status = useAuditStatus(activeAuditId)

  const startAudit = useCallback(async () => {
    const result = await trigger.mutateAsync()
    const id = result.audit_id
    setActiveAuditId(id)
    localStorage.setItem('shopiq_active_audit', id)
  }, [trigger])

  // Clear stored ID once complete so next visit loads fresh
  useEffect(() => {
    if (status.data?.status === 'complete') {
      localStorage.setItem('shopiq_active_audit', activeAuditId ?? '')
    }
  }, [status.data?.status, activeAuditId])

  return {
    activeAuditId,
    setActiveAuditId,
    startAudit,
    isTriggering: trigger.isPending,
    triggerError: trigger.error,
    statusData: status.data,
    isPolling: status.isFetching,
  }
}
