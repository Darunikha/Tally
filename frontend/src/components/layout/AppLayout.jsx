import { useEffect, useRef, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AlertTriangle, Bell, ChevronDown, Loader2, LogOut, MailWarning, Menu, Search, Settings, X } from 'lucide-react'
import { api, errorMessage } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import { useFilters } from '../../context/FilterContext'
import { formatDate, formatINR, initials } from '../../lib/format'
import Sidebar, { Logo } from './Sidebar'
import { SeverityBadge } from '../ui'

function useClickAway(ref, fn) {
  useEffect(() => {
    const h = (e) => ref.current && !ref.current.contains(e.target) && fn()
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [ref, fn])
}

function Notifications({ data }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useClickAway(ref, () => setOpen(false))
  const items = (data?.items || []).filter((a) => a.status === 'open').slice(0, 5)
  const count = data?.counts?.open || 0
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} className="relative grid h-11 w-11 place-items-center rounded-full text-ink-soft transition hover:bg-white" aria-label={`Notifications (${count} open anomalies)`}>
        <Bell className="h-5 w-5" />
        {count > 0 && <span className="absolute right-2.5 top-2.5 h-2.5 w-2.5 rounded-full bg-danger-500 ring-2 ring-canvas" />}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-2xl border border-line bg-white p-2 shadow-pop animate-fade-up">
          <p className="px-3 pb-2 pt-2 text-sm font-bold text-ink">Needs your review</p>
          {items.length === 0 ? (
            <p className="px-3 pb-3 text-sm text-ink-muted">You're all caught up - no open anomalies.</p>
          ) : items.map((a) => (
            <Link key={a.key} to="/anomalies" onClick={() => setOpen(false)} className="flex gap-3 rounded-xl px-3 py-2.5 hover:bg-canvas">
              <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${a.severity === 'high' ? 'text-danger-500' : 'text-warn-500'}`} />
              <div className="min-w-0">
                <div className="flex items-center gap-2"><p className="truncate text-sm font-semibold text-ink">{a.type_label}</p><SeverityBadge severity={a.severity} /></div>
                <p className="line-clamp-2 text-xs text-ink-muted">{formatDate(a.date)} · {formatINR(a.amount)} · {a.reason}</p>
              </div>
            </Link>
          ))}
          <Link to="/anomalies" onClick={() => setOpen(false)} className="mt-1 block rounded-xl px-3 py-2 text-center text-sm font-semibold text-brand-600 hover:bg-brand-50">View all anomalies</Link>
        </div>
      )}
    </div>
  )
}

function VerifyBanner() {
  const { user } = useAuth()
  const [state, setState] = useState({ busy: false, msg: '', hidden: false })
  if (!user || user.email_verified || state.hidden) return null
  const resend = async () => {
    setState((s) => ({ ...s, busy: true }))
    try { setState({ busy: false, msg: (await api.post('/auth/resend-verification')).data.message, hidden: false }) } catch (e) { setState({ busy: false, msg: errorMessage(e), hidden: false }) }
  }
  return (
    <div className="mb-5 flex flex-wrap items-center gap-3 rounded-2xl border border-warn-100 bg-warn-50 px-4 py-3 text-sm" role="status">
      <MailWarning className="h-5 w-5 shrink-0 text-warn-500" />
      <p className="min-w-0 flex-1 text-ink-soft">{state.msg || <>Please verify your email address - we sent a link to <b className="text-ink">{user.email}</b>.</>}</p>
      <button className="btn-secondary btn-sm" onClick={resend} disabled={state.busy}>{state.busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}Resend link</button>
      <button className="rounded-lg p-1 text-ink-faint hover:bg-white hover:text-ink" onClick={() => setState((s) => ({ ...s, hidden: true }))} aria-label="Dismiss"><X className="h-4 w-4" /></button>
    </div>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useClickAway(ref, () => setOpen(false))
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} className="flex items-center gap-1.5 rounded-full p-1 pr-1.5 hover:bg-white" aria-label="Account menu">
        <span className="grid h-10 w-10 place-items-center rounded-full bg-brand-800 text-sm font-bold text-white">{initials(user?.full_name)}</span>
        <ChevronDown className="hidden h-4 w-4 text-ink-muted sm:block" />
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-60 rounded-2xl border border-line bg-white p-2 shadow-pop animate-fade-up">
          <div className="px-3 py-2">
            <p className="truncate text-sm font-bold text-ink">{user?.full_name}</p>
            <p className="truncate text-xs text-ink-muted">{user?.email}</p>
          </div>
          <Link to="/settings" onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-ink-soft hover:bg-canvas"><Settings className="h-4 w-4" />Settings</Link>
          <button onClick={logout} className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-danger-500 hover:bg-danger-50"><LogOut className="h-4 w-4" />Sign out</button>
        </div>
      )}
    </div>
  )
}

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [q, setQ] = useState('')
  const [anomalies, setAnomalies] = useState(null)
  const { version } = useFilters()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => { api.get('/anomalies', { params: { status: 'open' } }).then((r) => setAnomalies(r.data)).catch(() => {}) }, [version, location.pathname])
  useEffect(() => { window.scrollTo(0, 0) }, [location.pathname])

  const submit = (e) => {
    e.preventDefault()
    navigate(`/transactions?search=${encodeURIComponent(q.trim())}`)
  }

  return (
    <div className="min-h-screen bg-canvas">
      <div className="pointer-events-none fixed inset-0 -z-0 bg-[radial-gradient(60rem_30rem_at_85%_-10%,rgba(47,125,85,0.07),transparent)]" />
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} badge={anomalies?.counts?.open || 0} />
      <div className="relative lg:pl-[17rem]">
        <header className="sticky top-0 z-20 border-b border-transparent bg-canvas/85 backdrop-blur-md">
          <div className="mx-auto flex max-w-[1400px] items-center gap-2 px-4 py-3 sm:gap-3 sm:px-6 lg:px-8 lg:py-4">
            <button className="rounded-xl p-2 text-ink-soft hover:bg-white lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
            <Logo className="mr-auto lg:hidden [&_span]:text-lg [&_svg]:h-7 [&_svg]:w-7" />
            <form onSubmit={submit} className="hidden max-w-xl flex-1 md:block" role="search">
              <label className="relative block">
                <span className="sr-only">Search transactions</span>
                <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-muted" />
                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search transactions…" maxLength={100}
                  className="h-12 w-full rounded-2xl border border-line bg-white pl-12 pr-4 text-sm shadow-sm transition placeholder:text-ink-faint focus:border-brand-300 focus:outline-none focus:ring-4 focus:ring-brand-100" />
              </label>
            </form>
            <div className="ml-auto flex items-center gap-1 sm:gap-2">
              <button className="grid h-11 w-11 place-items-center rounded-full text-ink-soft hover:bg-white md:hidden" onClick={() => navigate('/transactions')} aria-label="Search transactions"><Search className="h-5 w-5" /></button>
              <Notifications data={anomalies} />
              <UserMenu />
            </div>
          </div>
        </header>
        <main className="mx-auto min-w-0 max-w-[1400px] px-4 pb-16 pt-2 sm:px-6 lg:px-8">
          <VerifyBanner />
          <Outlet />
        </main>
      </div>
    </div>
  )
}
