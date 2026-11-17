import { useEffect, useState } from 'react'
import { Loader2, RotateCcw } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import { useToast } from '../context/ToastContext'
import { formatDate, formatDateTime, formatINR } from '../lib/format'
import { Badge, CategoryPill, Modal, TypeBadge } from './ui'

export function MerchantAvatar({ name, color, size = 'md' }) {
  const s = size === 'sm' ? 'h-9 w-9 text-xs' : 'h-10 w-10 text-sm'
  const letter = (name || '?').replace(/[^A-Za-z0-9]/g, '').charAt(0).toUpperCase() || '?'
  return (
    <span className={`grid ${s} shrink-0 place-items-center rounded-full font-bold`}
      style={{ background: `${color || '#B8B2A7'}22`, color: color || '#6B7280' }} aria-hidden="true">
      {letter}
    </span>
  )
}

export function useCategories(deps = []) {
  const [cats, setCats] = useState([])
  useEffect(() => { api.get('/categories').then((r) => setCats(r.data)).catch(() => {}) }, deps) // eslint-disable-line react-hooks/exhaustive-deps
  return cats
}

const SOURCE_LABEL = { rule: 'Default rule', custom_rule: 'Your rule', manual: 'Set by you', default: 'Not recognised' }

export default function TransactionDetail({ txn, categories, onClose, onSaved }) {
  const toast = useToast()
  const [categoryId, setCategoryId] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [full, setFull] = useState(null)

  useEffect(() => {
    if (!txn) return
    setCategoryId(txn.category_id || '')
    setNotes(txn.notes || '')
    setFull(null)
    api.get(`/transactions/${txn.id}`).then((r) => setFull(r.data)).catch(() => {})
  }, [txn])

  if (!txn) return null
  const t = full || txn

  const save = async (body) => {
    setBusy(true)
    try {
      const r = await api.patch(`/transactions/${txn.id}`, body)
      toast.success('Transaction updated')
      onSaved?.(r.data)
      onClose()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }

  const changed = categoryId !== (txn.category_id || '') || notes !== (txn.notes || '')
  const body = {}
  if (categoryId !== (txn.category_id || '')) body.category_id = categoryId
  if (notes !== (txn.notes || '')) body.notes = notes

  const rows = [
    ['Date', formatDate(t.transaction_date)],
    ['Value date', t.value_date ? formatDate(t.value_date) : null],
    ['Payment method', t.payment_method],
    ['UPI ID', t.upi_id],
    ['UPI flow', t.upi_flow === 'P2M' ? 'Merchant payment (P2M)' : t.upi_flow === 'P2A' ? 'Person / account (P2A)' : null],
    ['Reference', t.transaction_reference],
    ['Balance after', t.balance != null ? formatINR(t.balance, { decimals: true }) : null],
    ['Bank', t.bank_name],
    ['Imported', formatDateTime(t.created_at)],
  ].filter(([, v]) => v)

  return (
    <Modal open={!!txn} onClose={onClose} title="Transaction details" size="lg"
      footer={<>
        {t.manual_override && <button className="btn-ghost mr-auto" disabled={busy} onClick={() => save({ reset_category: true })}><RotateCcw className="h-4 w-4" />Let rules decide</button>}
        <button className="btn-secondary" onClick={onClose}>Close</button>
        <button className="btn-primary" disabled={!changed || busy} onClick={() => save(body)}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Save changes</button>
      </>}>
      <div className="flex items-start gap-4">
        <MerchantAvatar name={t.normalized_merchant} color={t.category_color} />
        <div className="min-w-0 flex-1">
          <p className="text-lg font-bold text-ink">{t.normalized_merchant}</p>
          <p className="break-words text-xs text-ink-muted">{t.raw_description}</p>
        </div>
        <div className="text-right">
          <p className={`text-xl font-extrabold ${t.transaction_type === 'credit' ? 'text-brand-600' : 'text-ink'}`}>{t.transaction_type === 'credit' ? '+' : '−'}{formatINR(t.amount, { decimals: true })}</p>
          <TypeBadge type={t.transaction_type} />
        </div>
      </div>

      <dl className="mt-5 grid grid-cols-1 gap-x-6 gap-y-3 rounded-xl bg-canvas p-4 text-sm sm:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="min-w-0"><dt className="text-xs text-ink-muted">{k}</dt><dd className="break-all font-medium text-ink">{v}</dd></div>
        ))}
        <div><dt className="text-xs text-ink-muted">Categorised by</dt><dd className="mt-0.5 flex items-center gap-2"><CategoryPill name={t.category_name} color={t.category_color} /><Badge tone={t.categorization_source === 'default' ? 'warn' : 'neutral'}>{SOURCE_LABEL[t.categorization_source] || t.categorization_source}</Badge></dd></div>
      </dl>

      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="td-cat">Category</label>
          <select id="td-cat" className="select" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <p className="mt-1.5 text-xs text-ink-muted">Manual changes always take priority over rules.</p>
        </div>
        <div>
          <label className="label" htmlFor="td-notes">Notes</label>
          <textarea id="td-notes" className="input min-h-[78px] resize-y" maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Add a note…" />
        </div>
      </div>

      {full?.raw_bank_fields && Object.keys(full.raw_bank_fields).length > 0 && (
        <details className="mt-5 rounded-xl border border-line p-3 text-sm">
          <summary className="cursor-pointer font-semibold text-ink-soft">Original statement fields</summary>
          <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {Object.entries(full.raw_bank_fields).map(([k, v]) => (
              <div key={k} className="min-w-0"><dt className="text-xs text-ink-muted">{k}</dt><dd className="break-all text-ink">{v || '—'}</dd></div>
            ))}
          </dl>
        </details>
      )}
    </Modal>
  )
}
