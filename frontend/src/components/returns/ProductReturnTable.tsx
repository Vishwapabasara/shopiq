import { ReturnProduct } from '../../lib/api'

const REASON_LABELS: Record<string, string> = {
  size_fit: 'Size/Fit', wrong_item: 'Wrong item', damaged: 'Damaged',
  quality: 'Quality', not_needed: 'Changed mind', fraud: 'Fraud',
  exchange: 'Exchange', other: 'Other',
}

function rateColor(rate: number) {
  if (rate >= 30) return 'text-red-600 bg-red-50'
  if (rate >= 15) return 'text-amber-700 bg-amber-50'
  return 'text-emerald-700 bg-emerald-50'
}

interface Props {
  products: ReturnProduct[]
  currency: string
}

export function ProductReturnTable({ products, currency }: Props) {
  const fmt = (n: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(n)

  if (products.length === 0) {
    return (
      <div className="card px-6 py-8 text-center">
        <p className="text-sm text-slate-400">No product-level return data available.</p>
      </div>
    )
  }

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          Top returned products
        </p>
        <p className="text-xs text-slate-400">{products.length} products</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-100 text-xs text-slate-500 font-medium">
              <th className="text-left px-5 py-3">Product</th>
              <th className="text-right px-4 py-3">Orders</th>
              <th className="text-right px-4 py-3">Returns</th>
              <th className="text-right px-4 py-3">Return rate</th>
              <th className="text-right px-4 py-3">Refund value</th>
              <th className="text-left px-4 py-3">Top reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {products.map(p => (
              <tr key={p.product_id} className="hover:bg-slate-50/60 transition-colors">
                <td className="px-5 py-3">
                  <div className="flex items-center gap-3">
                    {p.image_url ? (
                      <img src={p.image_url} alt={p.title} className="w-8 h-8 object-cover rounded flex-shrink-0 bg-slate-100" />
                    ) : (
                      <div className="w-8 h-8 rounded bg-slate-100 flex-shrink-0 flex items-center justify-center text-slate-300 text-xs">◈</div>
                    )}
                    <span className="font-medium text-slate-800 truncate max-w-[180px]">{p.title}</span>
                  </div>
                </td>
                <td className="text-right px-4 py-3 text-slate-600">{p.total_orders}</td>
                <td className="text-right px-4 py-3 text-slate-600">{p.total_returns}</td>
                <td className="text-right px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${rateColor(p.return_rate)}`}>
                    {p.return_rate}%
                  </span>
                </td>
                <td className="text-right px-4 py-3 text-slate-600">{fmt(p.refund_value)}</td>
                <td className="px-4 py-3 text-slate-500 text-xs">
                  {REASON_LABELS[p.top_reason] ?? p.top_reason}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
