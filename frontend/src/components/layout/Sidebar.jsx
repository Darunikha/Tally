import { Link, NavLink } from 'react-router-dom'
import {
  AlertTriangle, BarChart3, CloudUpload, History, House, List, PiggyBank, Settings, Tags, X, Zap,
} from 'lucide-react'

export const NAV = [
  { to: '/', label: 'Dashboard', icon: House, end: true },
  { to: '/upload', label: 'Upload Statement', icon: CloudUpload },
  { to: '/transactions', label: 'Transactions', icon: List },
  { to: '/upi', label: 'UPI Analysis', icon: Zap },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/anomalies', label: 'Anomalies', icon: AlertTriangle },
  { to: '/budgets', label: 'Budgets', icon: PiggyBank },
  { to: '/categories', label: 'Categories & Rules', icon: Tags },
  { to: '/statements', label: 'Statement History', icon: History },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Logo({ className = '' }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <svg viewBox="0 0 32 32" className="h-9 w-9" aria-hidden="true">
        <path d="M6 26C6 13 15 6 27 5c0 13-8 21-20 21H6Z" fill="#2F7D55" />
        <path d="M7 25 18 14" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <span className="text-[1.4rem] font-extrabold tracking-tight text-ink">Tally</span>
    </div>
  )
}

function NavItems({ onNavigate, badge }) {
  return (
    <nav className="space-y-1" aria-label="Main">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}
          className={({ isActive }) => `group flex items-center gap-3 rounded-xl px-4 py-2.5 text-[0.92rem] font-medium transition ${
            isActive ? 'bg-brand-100/80 text-ink shadow-[inset_0_0_0_1px_rgba(47,125,85,0.08)]' : 'text-ink-soft hover:bg-white hover:text-ink'}`}>
          {({ isActive }) => (<>
            <Icon className={`h-5 w-5 ${isActive ? 'text-brand-600' : 'text-ink-muted group-hover:text-brand-500'}`} strokeWidth={isActive ? 2.4 : 2} />
            <span className="flex-1">{label}</span>
            {to === '/anomalies' && badge > 0 && (
              <span className="rounded-full bg-danger-500 px-1.5 py-0.5 text-[10px] font-bold leading-none text-white">{badge}</span>
            )}
          </>)}
        </NavLink>
      ))}
    </nav>
  )
}

function SidebarFooter() {
  return (
    <div className="relative mt-auto overflow-hidden rounded-2xl bg-gradient-to-br from-brand-50 to-white p-4 ring-1 ring-brand-100">
      <p className="text-sm font-bold text-ink">Spend smarter</p>
      <p className="mt-1 text-xs leading-relaxed text-ink-muted">Your statements are parsed on this server only - never shared with third parties.</p>
      <p className="relative z-10 mt-2 text-xs"><Link to="/privacy" className="font-semibold text-brand-700 hover:underline">Privacy</Link><span className="mx-1.5 text-ink-faint">·</span><Link to="/terms" className="font-semibold text-brand-700 hover:underline">Terms</Link></p>
      <svg viewBox="0 0 80 80" className="absolute -bottom-3 -right-3 h-16 w-16 opacity-25" aria-hidden="true">
        <path d="M10 70C10 35 35 12 70 10c0 35-22 60-58 60H10Z" fill="#2F7D55" />
      </svg>
    </div>
  )
}

export default function Sidebar({ mobileOpen, onClose, badge }) {
  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[17rem] flex-col border-r border-line bg-[#F9F9F5] px-4 py-6 lg:flex">
        <Logo className="mb-8 px-3" />
        <NavItems badge={badge} />
        <div className="mt-6 flex flex-1 flex-col"><SidebarFooter /></div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-ink/30 backdrop-blur-[2px]" onClick={onClose} />
          <aside className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-[#F9F9F5] px-4 py-5 shadow-pop animate-fade-up">
            <div className="mb-6 flex items-center justify-between px-2">
              <Logo />
              <button onClick={onClose} className="rounded-lg p-1.5 text-ink-muted hover:bg-white" aria-label="Close menu"><X className="h-5 w-5" /></button>
            </div>
            <div className="scrollbar-thin flex-1 overflow-y-auto"><NavItems onNavigate={onClose} badge={badge} /></div>
          </aside>
        </div>
      )}
    </>
  )
}
