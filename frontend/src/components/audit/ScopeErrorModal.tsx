interface ScopeErrorModalProps {
  missingScopes: string[]
  shopDomain: string
  onClose: () => void
}

const SCOPE_LABELS: Record<string, string> = {
  read_products: 'Read products',
  write_products: 'Write products',
  read_orders: 'Read orders',
  read_customers: 'Read customers',
}

export function ScopeErrorModal({ missingScopes, shopDomain, onClose }: ScopeErrorModalProps) {
  const reinstallUrl = `/auth/shopify/install?shop=${shopDomain}`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-xl max-w-md w-full p-6 z-10">
        {/* Icon */}
        <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center mx-auto mb-4">
          <span className="text-2xl">🔐</span>
        </div>

        <h2 className="text-lg font-semibold text-slate-900 text-center mb-2">
          Permissions need updating
        </h2>
        <p className="text-sm text-slate-500 text-center mb-5">
          ShopIQ needs additional permissions to audit your store. This takes just a few seconds to fix.
        </p>

        {/* Missing scopes list */}
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-5">
          <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-2">
            Missing permissions
          </p>
          <ul className="space-y-1">
            {missingScopes.map(scope => (
              <li key={scope} className="flex items-center gap-2 text-sm text-amber-800">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                {SCOPE_LABELS[scope] ?? scope}
              </li>
            ))}
          </ul>
        </div>

        <div className="flex flex-col gap-2">
          <a
            href={`${import.meta.env.VITE_API_URL || 'https://shopiq-production.up.railway.app'}${reinstallUrl}`}
            className="btn-primary text-center py-2.5 rounded-lg text-sm font-medium"
          >
            Grant permissions
          </a>
          <button
            onClick={onClose}
            className="text-sm text-slate-400 hover:text-slate-600 py-2 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
