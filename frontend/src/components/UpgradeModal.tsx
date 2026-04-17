import { useNavigate } from 'react-router-dom'

interface UpgradeModalProps {
  reason: string
  message: string
  onClose: () => void
}

export function UpgradeModal({ message, onClose }: UpgradeModalProps) {
  const navigate = useNavigate()

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-white rounded-2xl shadow-xl max-w-sm w-full p-6 z-10">
        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-brand-500 to-purple-500 flex items-center justify-center mx-auto mb-4">
          <span className="text-white text-xl">⚡</span>
        </div>

        <h2 className="text-lg font-semibold text-slate-900 text-center mb-2">
          Upgrade to continue
        </h2>
        <p className="text-sm text-slate-500 text-center mb-5">{message}</p>

        {/* Pro plan highlight */}
        <div className="bg-gradient-to-r from-brand-600 to-purple-600 text-white rounded-xl p-4 mb-5">
          <p className="font-semibold text-sm mb-1">✨ Professional Plan</p>
          <p className="text-2xl font-bold mb-2">
            $29 <span className="text-sm font-normal opacity-80">/month</span>
          </p>
          <ul className="text-xs space-y-1 opacity-90">
            <li>✓ 50 audits per month</li>
            <li>✓ Up to 1,000 products</li>
            <li>✓ AI-powered scoring</li>
            <li>✓ 7-day free trial — cancel anytime</li>
          </ul>
        </div>

        <div className="flex flex-col gap-2">
          <button
            onClick={() => { onClose(); navigate('/plans') }}
            className="btn-primary w-full py-2.5 text-sm"
          >
            View all plans
          </button>
          <button
            onClick={onClose}
            className="text-sm text-slate-400 hover:text-slate-600 py-2 transition-colors"
          >
            Maybe later
          </button>
        </div>
      </div>
    </div>
  )
}
