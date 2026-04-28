import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { authApi } from '../../lib/api'
import { cn } from '../../lib/utils'
import logo from '../../assets/shopiq-lettermark-1200.png'

// ── Inline SVG icons (no extra dependency) ────────────────────────────────────
const Icons = {
  audit: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
    </svg>
  ),
  returns: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="1 4 1 10 7 10"/>
      <path d="M3.51 15a9 9 0 1 0 .49-3.01"/>
    </svg>
  ),
  stock: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
      <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
    </svg>
  ),
  price: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>
      <line x1="7" y1="7" x2="7.01" y2="7"/>
    </svg>
  ),
  copy: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
    </svg>
  ),
  star: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
    </svg>
  ),
  leads: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    </svg>
  ),
  invoice: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
    </svg>
  ),
  contract: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
  ),
  onboard: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
      <polyline points="22 4 12 14.01 9 11.01"/>
    </svg>
  ),
  logout: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
      <polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
    </svg>
  ),
  newTab: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
      <polyline points="15 3 21 3 21 9"/>
      <line x1="10" y1="14" x2="21" y2="3"/>
    </svg>
  ),
}

const NAV_ECOMMERCE = [
  { to: '/dashboard',          icon: Icons.audit,    label: 'ShopAudit AI',  active: true  },
  { to: '/dashboard/stock',    icon: Icons.stock,    label: 'StockSense',    active: true  },
  { to: '/dashboard/returns',  icon: Icons.returns,  label: 'ReturnRadar',   active: true  },
  { to: '/dashboard/price',    icon: Icons.price,    label: 'PricePulse',    active: true  },
  { to: '/dashboard/copy',     icon: Icons.copy,     label: 'BulkCopy AI',   active: true  },
]

const NAV_OPS = [
  { to: '/dashboard/reviews',  icon: Icons.star,     label: 'ReviewReply',   active: true  },
  { to: '/dashboard/leads',    icon: Icons.leads,    label: 'LeadForge',     active: false },
  { to: '/dashboard/invoice',  icon: Icons.invoice,  label: 'InvoiceFlow',   active: false },
  { to: '/dashboard/contract', icon: Icons.contract, label: 'ContractPilot', active: false },
  { to: '/dashboard/onboard',  icon: Icons.onboard,  label: 'OnboardKit',    active: false },
]

function buildStandaloneUrl() {
  const shop = sessionStorage.getItem('shopiq_shop') || localStorage.getItem('shopiq_shop')
  const host = sessionStorage.getItem('shopiq_host') || localStorage.getItem('shopiq_host')
  const qs = new URLSearchParams()
  if (shop) qs.set('shop', shop)
  if (host) qs.set('host', host)
  const q = qs.toString()
  return `${window.location.origin}${window.location.pathname}${q ? '?' + q : ''}`
}

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
      <div className="px-5 py-4 border-b border-slate-100">
        <div className="flex items-center gap-2.5">
          <img src={logo} alt="ShopIQ" className="w-8 h-8 object-contain flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="font-semibold text-slate-900 tracking-tight text-sm">ShopIQ</span>
            <p className="text-[10px] text-slate-400 leading-tight">Shopify Intelligence</p>
          </div>
          <button
            onClick={() => window.open(buildStandaloneUrl(), '_blank', 'noopener,noreferrer')}
            className="text-slate-400 hover:text-slate-600 transition-colors flex-shrink-0"
            title="Open in new tab"
          >
            {Icons.newTab}
          </button>
        </div>
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
            className="text-slate-400 hover:text-slate-600 transition-colors"
            title="Sign out"
          >
            {Icons.logout}
          </button>
        </div>
      </div>
    </aside>
  )
}

type NavItem = { to: string; icon: React.ReactNode; label: string; active: boolean }

function NavSection({ label, items }: { label: string; items: NavItem[] }) {
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

function ActiveNavItem({ item }: { item: NavItem }) {
  const { search } = useLocation()
  const current = new URLSearchParams(search)
  const qs = new URLSearchParams()
  const shop = current.get('shop') || sessionStorage.getItem('shopiq_shop') || localStorage.getItem('shopiq_shop')
  const host = current.get('host') || sessionStorage.getItem('shopiq_host') || localStorage.getItem('shopiq_host')
  if (shop) qs.set('shop', shop)
  if (host) qs.set('host', host)
  const to = qs.size > 0 ? `${item.to}?${qs.toString()}` : item.to

  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) => cn(
        'flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition-colors',
        isActive
          ? 'bg-brand-50 text-brand-700 font-medium'
          : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
      )}
    >
      <span className="flex-shrink-0 w-4 flex items-center justify-center">{item.icon}</span>
      <span>{item.label}</span>
    </NavLink>
  )
}

function ComingSoonItem({ item }: { item: NavItem }) {
  return (
    <div className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-slate-400 cursor-default">
      <span className="flex-shrink-0 w-4 flex items-center justify-center">{item.icon}</span>
      <span>{item.label}</span>
      <span className="ml-auto text-[9px] font-medium bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded border border-amber-100">
        Soon
      </span>
    </div>
  )
}
