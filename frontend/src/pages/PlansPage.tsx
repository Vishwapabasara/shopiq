import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, billingApi } from '../lib/api'
import { Spinner } from '../components/ui'
import { cn } from '../lib/utils'

interface Plan {
  name: string
  price: number
  audits_per_month: number
  copy_generations_per_month?: number
  ai_fixes_per_month?: number
  audit_batch_size?: number
  features: string[]
  trial_days?: number
}

export function PlansPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const toDashboard = () => {
    const p = new URLSearchParams(window.location.search)
    const shop = p.get('shop') || sessionStorage.getItem('shopiq_shop') || ''
    const host = p.get('host') || sessionStorage.getItem('shopiq_host') || ''
    const qs = new URLSearchParams()
    if (shop) qs.set('shop', shop)
    if (host) qs.set('host', host)
    const q = qs.toString()
    navigate(q ? `/dashboard?${q}` : '/dashboard')
  }

  const { data: usageData, isLoading: usageLoading } = useQuery({
    queryKey: ['billing-usage'],
    queryFn: billingApi.getUsage,
    staleTime: 30_000,
  })

  const { data: plansData, isLoading: plansLoading } = useQuery({
    queryKey: ['billing-plans'],
    queryFn: billingApi.plans,
    staleTime: Infinity,
  })

  const currentPlan = usageData?.plan ?? 'free'
  const plans = (plansData?.plans ?? {}) as Record<string, Plan>

  const handleSubscribe = async (planKey: string) => {
    if (planKey === currentPlan || loadingPlan) return
    setLoadingPlan(planKey)
    setError(null)
    try {
      const res = await api.post<{
        test_mode?: boolean
        scheduled?: boolean
        confirmation_url?: string
        plan?: string
        message?: string
      }>(`/billing/subscribe/${planKey}`).then(r => r.data)

      if (res.confirmation_url) {
        // Redirect to Shopify payment gateway
        window.top!.location.href = res.confirmation_url
        return
      }

      // DEV mode or scheduled downgrade — refresh data and go to dashboard
      await qc.invalidateQueries({ queryKey: ['me'] })
      await qc.invalidateQueries({ queryKey: ['billing-usage'] })
      await qc.invalidateQueries({ queryKey: ['account-profile'] })
      toDashboard()
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? 'Failed to subscribe. Please try again.'
      setError(msg)
    } finally {
      setLoadingPlan(null)
    }
  }

  if (usageLoading || plansLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
        <Spinner size={28} />
      </div>
    )
  }

  const planOrder = ['free', 'pro', 'enterprise']
  const orderedPlans = planOrder.filter(k => plans[k]).map(k => ({ key: k, plan: plans[k] }))

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-12 px-4">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <button
            onClick={toDashboard}
            className="text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 mb-6 inline-flex items-center gap-1 transition-colors"
          >
            ← Back to dashboard
          </button>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 mb-3">Choose Your Plan</h1>
          <p className="text-slate-500 dark:text-slate-400">Unlock the full power of ShopIQ</p>
        </div>

        {error && (
          <div className="mb-8 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl px-5 py-3 text-sm text-red-600 dark:text-red-400 text-center">
            {error}
          </div>
        )}

        {/* Plan cards */}
        <div className="grid md:grid-cols-3 gap-6">
          {orderedPlans.map(({ key, plan }) => {
            const isCurrent = key === currentPlan
            const isLoading = loadingPlan === key

            return (
              <div
                key={key}
                className={cn(
                  'bg-white dark:bg-slate-800 rounded-2xl shadow-sm border p-8 relative flex flex-col',
                  key === 'pro'
                    ? 'border-brand-500 ring-2 ring-brand-500 shadow-md'
                    : key === 'enterprise'
                    ? 'border-purple-300 dark:border-purple-700'
                    : 'border-slate-200 dark:border-slate-700'
                )}
              >
                {key === 'pro' && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                    <span className="bg-brand-600 text-white text-xs font-semibold px-3 py-1 rounded-full">
                      Most popular
                    </span>
                  </div>
                )}

                <div className="mb-6">
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-1">{plan.name}</h2>
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-bold text-slate-900 dark:text-slate-100">${plan.price}</span>
                    {plan.price > 0 && (
                      <span className="text-slate-400 dark:text-slate-500 text-sm">/month</span>
                    )}
                  </div>
                  {plan.trial_days && plan.price > 0 && (
                    <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-1 font-medium">
                      {plan.trial_days}-day free trial
                    </p>
                  )}
                </div>

                <ul className="space-y-2.5 mb-8 flex-1">
                  {plan.features.map((feature, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                      <span className="text-emerald-500 mt-0.5 flex-shrink-0">✓</span>
                      {feature}
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => handleSubscribe(key)}
                  disabled={!!loadingPlan || isCurrent}
                  className={cn(
                    'w-full py-2.5 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2',
                    isCurrent
                      ? 'bg-slate-100 dark:bg-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed'
                      : key === 'pro'
                      ? 'bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-60'
                      : key === 'enterprise'
                      ? 'bg-slate-900 dark:bg-purple-700 text-white hover:bg-slate-800 dark:hover:bg-purple-600 disabled:opacity-60'
                      : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600 disabled:opacity-60'
                  )}
                >
                  {isLoading && <Spinner size={14} className={key === 'free' ? 'text-slate-600' : 'text-white'} />}
                  {isCurrent
                    ? 'Current plan'
                    : isLoading
                    ? 'Processing…'
                    : key === 'free'
                    ? 'Downgrade to Free'
                    : `Upgrade to ${plan.name}`}
                </button>
              </div>
            )
          })}
        </div>

        <p className="text-center text-xs text-slate-400 dark:text-slate-500 mt-8">
          Billing is processed securely through Shopify. Cancel anytime.
        </p>
      </div>
    </div>
  )
}
