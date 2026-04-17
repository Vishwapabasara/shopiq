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

// ── Scope error type ──────────────────────────────────────────────────────────

export interface ScopeErrorData {
  error: 'missing_scopes'
  message: string
  missing_scopes: string[]
  action: 'reinstall'
}

function extractScopeError(err: unknown): ScopeErrorData | null {
  const data = (err as any)?.response?.data
  if ((err as any)?.response?.status === 403 && data?.error === 'missing_scopes') {
    return data as ScopeErrorData
  }
  return null
}

// ── Composed hook: manage active audit flow ───────────────────────────────────

export function useActiveAudit() {
  // ── Restore last audit ID from localStorage ──────────────────────────────
  const [activeAuditId, setActiveAuditId] = useState<string | null>(() =>
    localStorage.getItem('shopiq_active_audit')
  )
  const [scopeError, setScopeError] = useState<ScopeErrorData | null>(null)

  const trigger = useTriggerAudit()
  const status = useAuditStatus(activeAuditId)

  // ── Persist completed audit ID so results survive page refresh ────────────
  useEffect(() => {
    if (status.data?.status === 'complete' && activeAuditId) {
      localStorage.setItem('shopiq_active_audit', activeAuditId)
    }
  }, [status.data?.status, activeAuditId])

  // ── Clear stale "running" audits on mount ─────────────────────────────────
  // If the stored audit is stuck in queued/running (e.g. after a redeploy),
  // clear it so the user sees the empty state instead of a frozen spinner.
  useEffect(() => {
    if (
      status.data?.status === 'failed' ||
      // If we have an ID but the API says it doesn't exist (404 → status is undefined after error)
      (activeAuditId && status.isError)
    ) {
      localStorage.removeItem('shopiq_active_audit')
      setActiveAuditId(null)
    }
  }, [status.data?.status, status.isError, activeAuditId])

  // ── Start a brand new audit ───────────────────────────────────────────────
  const startAudit = useCallback(async () => {
    setScopeError(null)
    setActiveAuditId(null)
    localStorage.removeItem('shopiq_active_audit')

    try {
      const result = await trigger.mutateAsync()
      const id = result.audit_id
      setActiveAuditId(id)
      localStorage.setItem('shopiq_active_audit', id)
    } catch (err) {
      const se = extractScopeError(err)
      if (se) setScopeError(se)
      // non-scope errors: trigger.error is set — AuditPage renders the error banner
    }
  }, [trigger])

  const isRunning =
    status.data?.status === 'queued' || status.data?.status === 'running'

  return {
    activeAuditId,
    setActiveAuditId,
    startAudit,
    isTriggering: trigger.isPending,
    triggerError: scopeError ? null : trigger.error,  // suppress generic error when showing modal
    scopeError,
    clearScopeError: () => setScopeError(null),
    statusData: status.data,
    isPolling: status.isFetching,
    isRunning,
  }
}