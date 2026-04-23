import { FlaggedCustomer } from '../../lib/api'

function riskBadge(level: FlaggedCustomer['risk_level']) {
  return level === 'high'
    ? 'bg-red-50 text-red-700 border border-red-200'
    : 'bg-amber-50 text-amber-700 border border-amber-200'
}

interface Props { customers: FlaggedCustomer[] }

export function FlaggedCustomers({ customers }: Props) {
  if (customers.length === 0) return null

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
            Flagged customers
          </p>
          <span className="text-[10px] bg-red-50 text-red-600 border border-red-100 px-1.5 py-0.5 rounded font-medium">
            ≥ 30% return rate
          </span>
        </div>
        <p className="text-xs text-slate-400">{customers.length} flagged</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-100 text-xs text-slate-500 font-medium">
              <th className="text-left px-5 py-3">Customer</th>
              <th className="text-right px-4 py-3">Orders</th>
              <th className="text-right px-4 py-3">Returns</th>
              <th className="text-right px-4 py-3">Return rate</th>
              <th className="text-left px-4 py-3">Risk</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {customers.map(c => (
              <tr key={c.customer_id} className="hover:bg-slate-50/60 transition-colors">
                <td className="px-5 py-3">
                  <p className="font-medium text-slate-800">{c.name || 'Guest'}</p>
                  <p className="text-xs text-slate-400">{c.email}</p>
                </td>
                <td className="text-right px-4 py-3 text-slate-600">{c.total_orders}</td>
                <td className="text-right px-4 py-3 text-slate-600">{c.total_returns}</td>
                <td className="text-right px-4 py-3 font-semibold text-red-600">{c.return_rate}%</td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold capitalize ${riskBadge(c.risk_level)}`}>
                    {c.risk_level}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
