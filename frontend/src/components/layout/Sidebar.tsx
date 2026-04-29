import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { authApi, api } from '../../lib/api'
import { cn } from '../../lib/utils'
import { useTheme } from '../../contexts/ThemeContext'
import logo from '../../assets/shopiq-lettermark-1200.png'

const PLAN_BADGE: Record<string, { label: string; cls: string }> = {
  free:       { label: 'Free',       cls: 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400' },
  pro:        { label: 'Pro',        cls: 'bg-brand-50 text-brand-600 dark:bg-brand-900 dark:text-brand-400' },
  enterprise: { label: 'Enterprise', cls: 'bg-purple-50 text-purple-600 dark:bg-purple-900 dark:text-purple-400' },
  starter:    { label: 'Free',       cls: 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400' },
}

const Icons = {
  audit: (<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>),
  returns: (<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.01"/></svg>),
  stock: (<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>),
  price: (<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>),
  copy: (<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>),
  star: (<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>),
  logout: (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>),
  newTab: (<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>),
  moon: (<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>),
  sun: (<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>),
  close: (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>),
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
]

function buildStandaloneUrl() {
  const shop = sessionStorage.getItem('shopiq_shop') || localStorage.getItem('shopiq_shop')
  const host = sessionStorage.getItem('shopiq_host') || localStorage.getItem('shopiq_host')
  // Route through the backend so it sets a first-party session cookie before
  // redirecting to the frontend — avoids third-party cookie issues in new tabs.
  const apiUrl = import.meta.env.VITE_API_URL || 'https://shopiq-production.up.railway.app'
  const qs = new URLSearchParams()
  if (shop) qs.set('shop', shop)
  if (host) qs.set('host', host)
  return `${apiUrl}/auth/open-standalone?${qs.toString()}`
}

interface SidebarProps {
  mobileOpen?: boolean
  onMobileClose?: () => void
}

export function Sidebar({ mobileOpen = false, onMobileClose }: SidebarProps) {
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: authApi.me })
  const { data: usageData } = useQuery({
    queryKey: ['billing-usage'],
    queryFn: () => api.get('/billing/usage').then(r => r.data),
    staleTime: 60_000,
  })
  const navigate = useNavigate()
  const { theme, toggle } = useTheme()

  const initials = (me?.shop_name ?? 'SQ')
    .split(' ').map((w: string) => w[0]).join('').toUpperCase().slice(0, 2)

  const plan = (me?.plan ?? 'free') as string
  const badge = PLAN_BADGE[plan] ?? PLAN_BADGE.free

  const sidebarContent = (
    <aside className="w-56 flex-shrink-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col h-full">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2.5">
          <img src={logo} alt="ShopIQ" className="w-8 h-8 object-contain flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="font-semibold text-slate-900 dark:text-slate-100 tracking-tight text-sm">ShopIQ</span>
            <p className="text-[10px] text-slate-400 dark:text-slate-500 leading-tight">Shopify Intelligence</p>
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            <button onClick={toggle} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors" title={theme === 'dark' ? 'Light mode' : 'Dark mode'}>
              {theme === 'dark' ? Icons.sun : Icons.moon}
            </button>
            <button onClick={() => window.open(buildStandaloneUrl(), '_blank', 'noopener,noreferrer')} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors hidden lg:block" title="Open in new tab">
              {Icons.newTab}
            </button>
            {/* Close button — mobile only */}
            {onMobileClose && (
              <button onClick={onMobileClose} className="lg:hidden text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors ml-1">
                {Icons.close}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Store pill */}
      <div className="px-3 py-3 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800 rounded-lg px-3 py-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" />
          <span className="text-xs text-slate-600 dark:text-slate-300 truncate font-medium flex-1 min-w-0">
            {me?.shop_name ?? me?.shop_domain ?? 'Your store'}
          </span>
          <span className={cn('text-[10px] font-semibold px-1.5 py-0.5 rounded flex-shrink-0', badge.cls)}>
            {badge.label}
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-4">
        <NavSection label="E-commerce" items={NAV_ECOMMERCE} onNavClick={onMobileClose} />
        <NavSection label="Operations" items={NAV_OPS} onNavClick={onMobileClose} />
      </nav>

      {/* Usage quick-view for free plan */}
      {(plan === 'free' || plan === 'starter') && usageData && (
        <div className="px-3 pb-2">
          <div className="bg-slate-50 dark:bg-slate-800 rounded-lg px-3 py-2.5 space-y-1.5">
            <p className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1">This month</p>
            <QuickUsageRow label="Audits" used={usageData.usage?.audits_used ?? 0} limit={usageData.limits?.audits_per_month ?? 10} />
            <QuickUsageRow label="Copy AI" used={usageData.usage?.copy_generations_used ?? 0} limit={usageData.limits?.copy_generations_per_month ?? 10} />
          </div>
        </div>
      )}

      {/* User footer */}
      <div className="border-t border-slate-100 dark:border-slate-800 px-3 py-3">
        <div className="flex items-center gap-2.5">
          <NavLink
            to="/dashboard/account"
            onClick={onMobileClose}
            className="flex items-center gap-2.5 flex-1 min-w-0 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 px-1 py-0.5 -mx-1 transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-brand-100 dark:bg-brand-900 flex items-center justify-center flex-shrink-0">
              <span className="text-brand-700 dark:text-brand-300 text-xs font-semibold">{initials}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-700 dark:text-slate-300 truncate">
                {me?.shop_name ?? me?.shop_domain}
              </p>
              <p className="text-xs text-slate-400 dark:text-slate-500 capitalize">{badge.label} plan</p>
            </div>
          </NavLink>
          <button
            onClick={() => authApi.logout().then(() => navigate('/login'))}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors flex-shrink-0"
            title="Sign out"
          >
            {Icons.logout}
          </button>
        </div>
      </div>
    </aside>
  )

  return (
    <>
      {/* Desktop: always visible */}
      <div className="hidden lg:flex h-screen sticky top-0">
        {sidebarContent}
      </div>

      {/* Mobile: slide-in drawer */}
      <div className={cn(
        'lg:hidden fixed inset-0 z-40 transition-all duration-200',
        mobileOpen ? 'pointer-events-auto' : 'pointer-events-none'
      )}>
        {/* Backdrop */}
        <div
          className={cn('absolute inset-0 bg-black/50 transition-opacity duration-200', mobileOpen ? 'opacity-100' : 'opacity-0')}
          onClick={onMobileClose}
        />
        {/* Drawer */}
        <div className={cn(
          'absolute inset-y-0 left-0 h-full transition-transform duration-200',
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}>
          {sidebarContent}
        </div>
      </div>
    </>
  )
}

function QuickUsageRow({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = limit === -1 ? 0 : Math.min((used / limit) * 100, 100)
  const color = pct >= 90 ? 'bg-red-400' : pct >= 70 ? 'bg-amber-400' : 'bg-brand-400'
  return (
    <div>
      <div className="flex justify-between text-[10px] text-slate-500 dark:text-slate-400 mb-0.5">
        <span>{label}</span>
        <span>{used}/{limit === -1 ? '∞' : limit}</span>
      </div>
      <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1">
        <div className={`h-1 rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

type NavItem = { to: string; icon: React.ReactNode; label: string; active: boolean }

function NavSection({ label, items, onNavClick }: { label: string; items: NavItem[]; onNavClick?: () => void }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest px-2 mb-1.5">{label}</p>
      <div className="space-y-0.5">
        {items.map(item => (
          item.active
            ? <ActiveNavItem key={item.to} item={item} onNavClick={onNavClick} />
            : <ComingSoonItem key={item.to} item={item} />
        ))}
      </div>
    </div>
  )
}

function ActiveNavItem({ item, onNavClick }: { item: NavItem; onNavClick?: () => void }) {
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
      onClick={onNavClick}
      className={({ isActive }) => cn(
        'flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition-colors',
        isActive
          ? 'bg-brand-50 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300 font-medium'
          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100'
      )}
    >
      <span className="flex-shrink-0 w-4 flex items-center justify-center">{item.icon}</span>
      <span>{item.label}</span>
    </NavLink>
  )
}

function ComingSoonItem({ item }: { item: NavItem }) {
  return (
    <div className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-slate-400 dark:text-slate-600 cursor-default">
      <span className="flex-shrink-0 w-4 flex items-center justify-center">{item.icon}</span>
      <span>{item.label}</span>
      <span className="ml-auto text-[9px] font-medium bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-500 px-1.5 py-0.5 rounded border border-amber-100 dark:border-amber-800">Soon</span>
    </div>
  )
}
