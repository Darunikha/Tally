import { useEffect, useRef, useState } from 'react'
import { CalendarDays, ChevronDown, FileText, Landmark } from 'lucide-react'
import { useFilters } from '../../context/FilterContext'
import { MONTH_NAMES, formatDate } from '../../lib/format'
import { Segmented } from '../ui'

export function periodLabel(filter) {
  if (filter.mode === 'month' && filter.month) return `${MONTH_NAMES[filter.month - 1]} ${filter.year}`
  if (filter.mode === 'year' && filter.year) return `Year ${filter.year}`
  if (filter.mode === 'custom') return `${filter.start ? formatDate(filter.start) : '…'} – ${filter.end ? formatDate(filter.end) : '…'}`
  return 'All time'
}

export default function PeriodPicker({ showStatement = true }) {
  const { filter, setFilter, periods, statements, accounts } = useFilters()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(filter)
  const ref = useRef(null)

  useEffect(() => { if (open) setDraft(filter) }, [open]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const now = new Date()
  const years = [...new Set([...periods.months.map((m) => m.year), now.getFullYear()])].sort((a, b) => b - a)
  const hasData = (m, y) => periods.months.some((p) => p.month === m && p.year === y)
  const apply = () => { setFilter(draft); setOpen(false) }
  const stmt = statements.find((s) => s.id === filter.uploadId)
  const account = filter.accountId === 'none' ? { name: 'Unassigned' } : accounts.find((a) => a.id === filter.accountId)
  // statements offered depend on the account picked, so you can't choose a combination with no data
  const stmtChoices = statements.filter((s) => !draft.accountId || (draft.accountId === 'none' ? !s.account_id : s.account_id === draft.accountId))

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} className="btn-secondary h-11 min-w-0 max-w-full rounded-xl px-3.5 shadow-sm" aria-expanded={open} aria-haspopup="dialog">
        <CalendarDays className="h-4 w-4 text-ink-soft" />
        <span className="truncate">{periodLabel(filter)}</span>
        {account && <span className="hidden max-w-[9rem] truncate rounded-md bg-brand-50 px-1.5 text-xs text-brand-700 sm:inline">{account.name}</span>}
        {!account && stmt && <span className="hidden max-w-[9rem] truncate rounded-md bg-brand-50 px-1.5 text-xs text-brand-700 sm:inline">{stmt.bank_name}</span>}
        <ChevronDown className="h-4 w-4 text-ink-muted" />
      </button>
      {open && (
        <div role="dialog" aria-label="Choose period" className="absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-2xl border border-line bg-surface p-4 shadow-pop animate-fade-up">
          <Segmented size="sm" value={draft.mode} onChange={(mode) => setDraft((d) => ({ ...d, mode, year: d.year || years[0], month: d.month || now.getMonth() + 1 }))}
            options={[{ value: 'month', label: 'Month' }, { value: 'year', label: 'Year' }, { value: 'all', label: 'All time' }, { value: 'custom', label: 'Custom' }]} />

          {(draft.mode === 'month' || draft.mode === 'year') && (
            <div className="mt-4">
              <label className="label" htmlFor="pp-year">Year</label>
              <select id="pp-year" className="select" value={draft.year || ''} onChange={(e) => setDraft((d) => ({ ...d, year: Number(e.target.value) }))}>
                {years.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
          )}
          {draft.mode === 'month' && (
            <div className="mt-3 grid grid-cols-4 gap-1.5">
              {MONTH_NAMES.map((n, i) => {
                const active = draft.month === i + 1
                const data = hasData(i + 1, draft.year)
                return (
                  <button key={n} onClick={() => setDraft((d) => ({ ...d, month: i + 1 }))}
                    className={`relative rounded-lg py-2 text-xs font-semibold transition ${active ? 'bg-brand-solid text-white' : data ? 'bg-brand-50 text-brand-700 hover:bg-brand-100' : 'text-ink-faint hover:bg-canvas'}`}
                    title={data ? 'Has transactions' : 'No transactions'}>
                    {n.slice(0, 3)}
                  </button>
                )
              })}
            </div>
          )}
          {draft.mode === 'custom' && (
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div><label className="label" htmlFor="pp-s">From</label><input id="pp-s" type="date" className="input" value={draft.start} onChange={(e) => setDraft((d) => ({ ...d, start: e.target.value }))} /></div>
              <div><label className="label" htmlFor="pp-e">To</label><input id="pp-e" type="date" className="input" value={draft.end} min={draft.start || undefined} onChange={(e) => setDraft((d) => ({ ...d, end: e.target.value }))} /></div>
            </div>
          )}
          {showStatement && accounts.length > 0 && (
            <div className="mt-4">
              <label className="label" htmlFor="pp-ac"><Landmark className="mr-1 inline h-3 w-3" />Account</label>
              <select id="pp-ac" className="select" value={draft.accountId || ''} onChange={(e) => setDraft((d) => ({ ...d, accountId: e.target.value, uploadId: '' }))}>
                <option value="">All accounts</option>
                {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}{a.last4 ? ` ••${a.last4}` : ''}</option>)}
                <option value="none">Not filed under an account</option>
              </select>
            </div>
          )}
          {showStatement && (
            <div className="mt-4">
              <label className="label" htmlFor="pp-st"><FileText className="mr-1 inline h-3 w-3" />Statement</label>
              <select id="pp-st" className="select" value={draft.uploadId} onChange={(e) => setDraft((d) => ({ ...d, uploadId: e.target.value }))}>
                <option value="">All statements</option>
                {stmtChoices.map((s) => <option key={s.id} value={s.id}>{s.bank_name} · {s.file_name}</option>)}
              </select>
            </div>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <button className="btn-secondary btn-sm" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary btn-sm" onClick={apply} disabled={draft.mode === 'custom' && (!draft.start || !draft.end || draft.start > draft.end)}>Apply</button>
          </div>
        </div>
      )}
    </div>
  )
}
