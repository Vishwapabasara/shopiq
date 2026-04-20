import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../utils/api'

interface Plan {
  name: string
  price: number
  audits_per_month: number
  max_products: number
  features: string[]
  trial_days?: number
}

export function PlansPage() {
  const [plans, setPlans] = useState<Record<string, Plan>>({})
  const [currentPlan, setCurrentPlan] = useState<string>('free')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([
      apiClient.get('/billing/plans').then(d => setPlans(d.plans)),
      apiClient.get('/billing/usage').then(d => setCurrentPlan(d.plan)),
    ]).catch(console.error)
  }, [])

  const handleSubscribe = async (planType: string) => {
    setLoading(true)
    try {
      const response = await apiClient.post(`/billing/subscribe/${planType}`)

      if (response.test_mode) {
        alert(`✅ ${response.message}\n\n(Running in test mode — no charges will be made)`)
        setCurrentPlan(planType)
        navigate('/dashboard')
      } else if (response.confirmation_url) {
        window.top!.location.href = response.confirmation_url
      } else {
        setCurrentPlan(planType)
        navigate('/dashboard')
      }
    } catch (error: any) {
      console.error('Subscription error:', error)
      alert(error?.message ?? 'Failed to subscribe. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const planOrder = ['free', 'pro', 'enterprise']
  const orderedPlans = planOrder
    .filter(k => plans[k])
    .map(k => ({ key: k, plan: plans[k] }))

  return (
    <div className="min-h-screen bg-slate-50 py-12 px-4">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <button
            onClick={() => navigate('/dashboard')}
            className="text-sm text-slate-500 hover:text-slate-700 mb-6 inline-flex items-center gap-1"
          >
            ← Back to dashboard
          </button>
          <h1 className="text-3xl font-bold text-slate-900 mb-3">Choose Your Plan</h1>
          <p className="text-slate-500">Unlock the full power of ShopIQ</p>
        </div>

        {/* Plan cards */}
        <div className="grid md:grid-cols-3 gap-6">
          {orderedPlans.map(({ key, plan }) => (
            <div
              key={key}
              className={`bg-white rounded-2xl shadow-sm border p-8 relative flex flex-col ${
                key === 'pro'
                  ? 'border-brand-500 ring-2 ring-brand-500 shadow-md'
                  : 'border-slate-200'
              }`}
            >
              {key === 'pro' && (
                <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                  <span className="bg-brand-600 text-white text-xs font-semibold px-3 py-1 rounded-full">
                    Most popular
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h2 className="text-lg font-semibold text-slate-900 mb-1">{plan.name}</h2>
                <div className="flex items-baseline gap-1">
                  <span className="text-4xl font-bold text-slate-900">${plan.price}</span>
                  {plan.price > 0 && (
                    <span className="text-slate-400 text-sm">/month</span>
                  )}
                </div>
                {plan.trial_days && (
                  <p className="text-xs text-emerald-600 mt-1 font-medium">
                    {plan.trial_days}-day free trial
                  </p>
                )}
              </div>

              <ul className="space-y-2.5 mb-8 flex-1">
                {plan.features.map((feature, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                    <span className="text-emerald-500 mt-0.5 flex-shrink-0">✓</span>
                    {feature}
                  </li>
                ))}
              </ul>

              <button
                onClick={() => handleSubscribe(key)}
                disabled={loading || currentPlan === key}
                className={`w-full py-2.5 rounded-xl text-sm font-semibold transition ${
                  currentPlan === key
                    ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                    : key === 'pro'
                    ? 'bg-brand-600 text-white hover:bg-brand-700'
                    : key === 'enterprise'
                    ? 'bg-slate-900 text-white hover:bg-slate-800'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                {loading
                  ? 'Processing…'
                  : currentPlan === key
                  ? 'Current plan'
                  : key === 'free'
                  ? 'Downgrade to Free'
                  : `Upgrade to ${plan.name}`}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
