import { NavLink, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { authApi } from '../../lib/api'
import { cn } from '../../lib/utils'

const NAV_ECOMMERCE = [
  { to: '/dashboard',          icon: '◈', label: 'ShopAudit AI',  active: true  },
  { to: '/dashboard/returns',  icon: '↩', label: 'ReturnRadar',   active: false },
  { to: '/dashboard/stock',    icon: '⬡', label: 'StockSense',    active: false },
  { to: '/dashboard/price',    icon: '◉', label: 'PricePulse',    active: false },
  { to: '/dashboard/copy',     icon: '✦', label: 'BulkCopy AI',   active: false },
]

const NAV_OPS = [
  { to: '/dashboard/reviews',  icon: '★', label: 'ReviewReply',   active: false },
  { to: '/dashboard/leads',    icon: '◎', label: 'LeadForge',     active: false },
  { to: '/dashboard/invoice',  icon: '▤', label: 'InvoiceFlow',   active: false },
  { to: '/dashboard/contract', icon: '◻', label: 'ContractPilot', active: false },
  { to: '/dashboard/onboard',  icon: '▷', label: 'OnboardKit',    active: false },
]

export function Sidebar() {
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: authApi.me })
  const navigate = useNavigate()

  const initials = (me?.shop_name ?? 'SQ')
    .split(' ')
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  return (
    <aside className="w-56 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-100">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center">
            <span className="text-white text-xs font-bold">IQ</span>
          </div>
          <span className="font-semibold text-slate-900 tracking-tight">ShopIQ</span>
        </div>
        <p className="text-xs text-slate-400 mt-0.5 ml-9 -mt-0.5">Shopify Intelligence</p>
      </div>

      {/* Store pill */}
      <div className="px-3 py-3 border-b border-slate-100">
        <div className="flex items-center gap-2 bg-slate-50 rounded-lg px-3 py-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" />
          <span className="text-xs text-slate-600 truncate font-medium">
            {me?.shop_name ?? me?.shop_domain ?? 'Your store'}
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-4">
        <NavSection label="E-commerce" items={NAV_ECOMMERCE} />
        <NavSection label="Operations" items={NAV_OPS} />
      </nav>

      {/* User footer */}
      <div className="border-t border-slate-100 px-3 py-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center flex-shrink-0">
            <span className="text-brand-700 text-xs font-semibold">{initials}</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-slate-700 truncate">
              {me?.shop_name ?? me?.shop_domain}
            </p>
            <p className="text-xs text-slate-400 capitalize">{me?.plan ?? 'starter'} plan</p>
          </div>
          <button
            onClick={() => authApi.logout().then(() => navigate('/login'))}
            className="text-slate-400 hover:text-slate-600 transition-colors text-xs"
            title="Sign out"
          >
            ⏻
          </button>
        </div>
      </div>
    </aside>
  )
}

function NavSection({ label, items }: { label: string; items: typeof NAV_ECOMMERCE }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest px-2 mb-1.5">
        {label}
      </p>
      <div className="space-y-0.5">
        {items.map(item => (
          item.active
            ? <ActiveNavItem key={item.to} item={item} />
            : <ComingSoonItem key={item.to} item={item} />
        ))}
      </div>
    </div>
  )
}

function ActiveNavItem({ item }: { item: typeof NAV_ECOMMERCE[0] }) {
  return (
    <NavLink
      to={item.to}
      end
      className={({ isActive }) => cn(
        'flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition-colors',
        isActive
          ? 'bg-brand-50 text-brand-700 font-medium'
          : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
      )}
    >
      <span className="text-base leading-none w-4 text-center">{item.icon}</span>
      <span>{item.label}</span>
    </NavLink>
  )
}

function ComingSoonItem({ item }: { item: typeof NAV_ECOMMERCE[0] }) {
  return (
    <div className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-slate-400 cursor-default">
      <span className="text-base leading-none w-4 text-center">{item.icon}</span>
      <span>{item.label}</span>
      <span className="ml-auto text-[9px] font-medium bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded border border-amber-100">
        Soon
      </span>
    </div>
  )
}
