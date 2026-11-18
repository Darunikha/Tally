import { useEffect, useRef } from 'react'
import { AlertCircle, ArrowDownRight, ArrowUpRight, ChevronLeft, ChevronRight, Info, Loader2, X } from 'lucide-react'

export function Card({ className = '', children, ...rest }) {
  return <section className={`card ${className}`} {...rest}>{children}</section>
}

export function CardHeader({ icon: Icon, title, subtitle, action, className = '' }) {
  return (
    <div className={`mb-4 flex flex-wrap items-start justify-between gap-3 ${className}`}>
      <div className="flex min-w-0 items-center gap-2.5">
        {Icon && <Icon className="h-5 w-5 shrink-0 text-brand-500" strokeWidth={2.2} />}
        <div className="min-w-0">
          <h2 className="truncate text-base font-bold text-ink sm:text-lg">{title}</h2>
          {subtitle && <p className="text-xs text-ink-muted sm:text-sm">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  )
}

/** Change indicator. `goodWhenUp` decides colour (expenses up = bad). */
export function Delta({ value, goodWhenUp = true, suffix = 'vs prev.' }) {
  if (value == null) return <span className="text-xs text-ink-faint">No prior data</span>
  const up = value > 0
  const good = value === 0 ? null : up === goodWhenUp
  const Icon = up ? ArrowUpRight : ArrowDownRight
  const cls = good == null ? 'text-ink-muted' : good ? 'text-brand-600' : 'text-danger-500'
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-semibold ${cls}`} title={`${suffix}`}>
      <Icon className="h-3.5 w-3.5" strokeWidth={2.5} />
      {Math.abs(value).toFixed(Math.abs(value) < 10 ? 1 : 0)}%
      <span className="ml-1 font-medium text-ink-faint">{suffix}</span>
    </span>
  )
}

export function StatCard({ icon: Icon, label, value, delta, goodWhenUp, tone = 'brand', hint, loading }) {
  const tones = {
    brand: 'bg-brand-50 text-brand-600 ring-brand-100',
    danger: 'bg-danger-50 text-danger-500 ring-danger-100',
    navy: 'bg-navy-50 text-navy-500 ring-navy-100',
    warn: 'bg-warn-50 text-warn-500 ring-warn-100',
  }
  return (
    <Card className={`card-pad flex items-center gap-4 ${tone === 'danger' ? 'bg-gradient-to-br from-surface to-danger-50/60' : ''}`}>
      <div className={`grid h-12 w-12 shrink-0 place-items-center rounded-full ring-8 sm:h-14 sm:w-14 ${tones[tone]}`}>
        <Icon className="h-6 w-6" strokeWidth={2} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1 text-sm font-medium text-ink-muted">
          {label}
          {hint && <InfoTip text={hint} />}
        </p>
        {loading ? <div className="skeleton mt-1.5 h-8 w-32" /> : (
          <p className="truncate text-2xl font-extrabold tracking-tight text-ink sm:text-[1.7rem]">{value}</p>
        )}
        {delta !== undefined && !loading && <div className="mt-0.5"><Delta value={delta} goodWhenUp={goodWhenUp} /></div>}
      </div>
    </Card>
  )
}

export function InfoTip({ text }) {
  return (
    <span className="group relative inline-flex">
      <Info className="h-3.5 w-3.5 cursor-help text-ink-faint" tabIndex={0} aria-label={text} />
      <span role="tooltip" className="pointer-events-none absolute bottom-full -right-2 z-30 mb-2 hidden w-56 rounded-lg bg-ink px-3 py-2 text-xs font-normal normal-case tracking-normal text-white shadow-pop group-hover:block group-focus-within:block">
        {text}
      </span>
    </span>
  )
}

export function Badge({ children, tone = 'neutral', className = '' }) {
  const tones = {
    neutral: 'bg-canvas text-ink-soft ring-1 ring-line',
    brand: 'bg-brand-50 text-brand-700',
    danger: 'bg-danger-50 text-danger-600',
    warn: 'bg-warn-50 text-warn-500',
    navy: 'bg-navy-50 text-navy-600',
  }
  return <span className={`chip ${tones[tone]} ${className}`}>{children}</span>
}

export function CategoryPill({ name, color }) {
  if (!name) return <span className="text-xs text-ink-faint">—</span>
  return (
    <span className="chip max-w-full bg-canvas text-ink-soft ring-1 ring-line">
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color || '#B8B2A7' }} />
      <span className="truncate">{name}</span>
    </span>
  )
}

export function TypeBadge({ type }) {
  return type === 'credit' ? <Badge tone="brand">Credit</Badge> : <Badge tone="danger">Debit</Badge>
}

export function SeverityBadge({ severity }) {
  const map = { high: ['danger', 'High'], medium: ['warn', 'Medium'], low: ['neutral', 'Low'] }
  const [tone, label] = map[severity] || map.low
  return <Badge tone={tone}><span className={`h-1.5 w-1.5 rounded-full ${tone === 'danger' ? 'bg-danger-solid' : tone === 'warn' ? 'bg-warn-500' : 'bg-ink-faint'}`} />{label}</Badge>
}

export function Spinner({ className = 'h-5 w-5' }) {
  return <Loader2 className={`animate-spin text-brand-500 ${className}`} />
}

export function Skeleton({ className = 'h-4 w-full' }) {
  return <div className={`skeleton ${className}`} />
}

export function LoadingBlock({ rows = 4, className = '' }) {
  return (
    <div className={`space-y-3 ${className}`} aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className={`h-4 ${i % 2 ? 'w-4/5' : 'w-full'}`} />)}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, message, action, compact = false }) {
  return (
    <div className={`flex flex-col items-center justify-center text-center ${compact ? 'py-8' : 'py-14'}`}>
      {Icon && (
        <div className="mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-500">
          <Icon className="h-7 w-7" />
        </div>
      )}
      <h3 className="text-base font-bold text-ink">{title}</h3>
      {message && <p className="mt-1 max-w-sm text-sm text-ink-muted">{message}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center">
      <AlertCircle className="mb-3 h-8 w-8 text-danger-500" />
      <p className="text-sm font-semibold text-ink">Couldn't load this</p>
      <p className="mt-1 max-w-sm text-sm text-ink-muted">{message}</p>
      {onRetry && <button className="btn-secondary btn-sm mt-4" onClick={onRetry}>Try again</button>}
    </div>
  )
}

export function Modal({ open, onClose, title, children, footer, size = 'md' }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && onClose?.()
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    ref.current?.focus()
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = prev }
  }, [open, onClose])
  if (!open) return null
  const widths = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' }
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/30 backdrop-blur-[2px] sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title}
        className={`flex max-h-[92vh] w-full ${widths[size]} flex-col rounded-t-2xl bg-surface shadow-pop outline-none animate-fade-up sm:rounded-2xl`}>
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <h3 className="text-base font-bold text-ink">{title}</h3>
          <button className="rounded-lg p-1 max-sm:p-2.5 text-ink-faint hover:bg-canvas hover:text-ink" onClick={onClose} aria-label="Close"><X className="h-5 w-5" /></button>
        </div>
        <div className="scrollbar-thin overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export function ConfirmDialog({ open, title, message, confirmLabel = 'Confirm', danger = false, busy = false, onConfirm, onClose, children }) {
  return (
    <Modal open={open} onClose={busy ? undefined : onClose} title={title} size="sm"
      footer={<>
        <button className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button>
        <button className={danger ? 'btn-danger' : 'btn-primary'} onClick={onConfirm} disabled={busy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}{confirmLabel}
        </button>
      </>}>
      <p className="text-sm text-ink-soft">{message}</p>
      {children}
    </Modal>
  )
}

export function Pagination({ page, pages, total, pageSize, onPage }) {
  if (!total) return null
  const from = (page - 1) * pageSize + 1
  const to = Math.min(total, page * pageSize)
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm text-ink-muted">
      <span>Showing <b className="text-ink">{from}–{to}</b> of <b className="text-ink">{total.toLocaleString('en-IN')}</b></span>
      <div className="flex items-center gap-1">
        <button className="btn-secondary btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></button>
        <span className="px-2 font-medium text-ink">{page} / {pages}</span>
        <button className="btn-secondary btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></button>
      </div>
    </div>
  )
}

export function Segmented({ options, value, onChange, size = 'md' }) {
  return (
    <div className="inline-flex rounded-xl bg-canvas p-1 ring-1 ring-line" role="tablist">
      {options.map((o) => (
        <button key={o.value} role="tab" aria-selected={value === o.value} onClick={() => onChange(o.value)}
          className={`rounded-lg font-semibold transition ${size === 'sm' ? 'px-2.5 py-1 text-xs max-sm:py-2' : 'px-3.5 py-1.5 text-sm'} ${value === o.value ? 'bg-surface text-brand-700 shadow-sm' : 'text-ink-muted hover:text-ink'}`}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-extrabold tracking-tight text-ink sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-muted sm:text-base">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
