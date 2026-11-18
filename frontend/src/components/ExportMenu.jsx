import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Download, FileSpreadsheet, FileText, Loader2 } from 'lucide-react'
import { errorMessage } from '../api/client'
import { useToast } from '../context/ToastContext'
import { downloadFile } from '../lib/download'

const FORMATS = [
  { value: 'csv', label: 'CSV', hint: 'Plain table, opens anywhere', icon: FileText },
  { value: 'xlsx', label: 'Excel', hint: 'Dates and amounts ready to sort and sum', icon: FileSpreadsheet },
]

/** Export every transaction matching the page's filters (not only the visible page). */
export default function ExportMenu({ params, total }) {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const close = (e) => { if (!ref.current?.contains(e.target)) setOpen(false) }
    const esc = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc) }
  }, [open])

  const run = async (format) => {
    setOpen(false)
    setBusy(true)
    try {
      const name = await downloadFile('/transactions/export', { ...params, format }, `tally-transactions.${format}`)
      toast.success(`Downloaded ${name}`)
    } catch (e) { toast.error(errorMessage(e, 'Export failed')) } finally { setBusy(false) }
  }

  return (
    <div className="relative" ref={ref}>
      <button className="btn-secondary" onClick={() => setOpen((o) => !o)} disabled={busy} aria-haspopup="menu" aria-expanded={open}>
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
        {busy ? 'Exporting…' : 'Export'}
        <ChevronDown className="h-4 w-4 text-ink-muted" />
      </button>
      {open && (
        <div role="menu" aria-label="Export format" className="absolute right-0 z-40 mt-2 w-72 rounded-2xl border border-line bg-surface p-2 shadow-pop animate-fade-up">
          <p className="px-3 pb-1 pt-1.5 text-xs text-ink-muted">
            {total != null ? <>Exports all <b className="text-ink">{total.toLocaleString('en-IN')}</b> transaction{total === 1 ? '' : 's'} matching your filters.</> : 'Exports every transaction matching your filters.'}
          </p>
          {FORMATS.map(({ value, label, hint, icon: Icon }) => (
            <button key={value} role="menuitem" onClick={() => run(value)}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-canvas">
              <Icon className="h-5 w-5 shrink-0 text-brand-500" />
              <span><span className="block text-sm font-semibold text-ink">{label}</span><span className="block text-xs text-ink-muted">{hint}</span></span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
