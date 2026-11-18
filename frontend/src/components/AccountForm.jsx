import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import { Modal } from './ui'
import { useToast } from '../context/ToastContext'

export const ACCOUNT_SWATCHES = ['#2F7D55', '#2A78D6', '#EB6834', '#6250D6', '#EDA100', '#E87BA4', '#4B7F87', '#8A6D3B']
export const TYPE_LABEL = { bank: 'Bank account', credit_card: 'Credit card' }

/** Create or edit an account. `preset` pre-fills a new account (for example from the statement being imported). */
export default function AccountForm({ initial, preset, onClose, onSaved }) {
  const toast = useToast()
  const editing = !!initial
  const [form, setForm] = useState({
    name: initial?.name || preset?.name || '',
    account_type: initial?.account_type || preset?.account_type || 'bank',
    last4: initial?.last4 || '',
    color: initial?.color || '',
  })
  const [busy, setBusy] = useState(false)
  const typeLocked = editing || !!preset?.account_type
  const valid = form.name.trim().length > 0 && (form.last4 === '' || /^\d{4}$/.test(form.last4))

  const save = async () => {
    setBusy(true)
    try {
      let saved
      if (editing) {
        saved = (await api.patch(`/accounts/${initial.id}`, { name: form.name.trim(), last4: form.last4, ...(form.color ? { color: form.color } : {}) })).data
      } else {
        saved = (await api.post('/accounts', {
          name: form.name.trim(), account_type: form.account_type, bank_name: preset?.bank_name || undefined,
          last4: form.last4 || undefined, color: form.color || undefined,
        })).data
      }
      toast.success(editing ? 'Account updated' : 'Account created')
      onSaved(saved)
      onClose()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }

  return (
    <Modal open onClose={onClose} title={editing ? 'Edit account' : 'New account'} size="sm"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={!valid || busy} onClick={save}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Save</button></>}>
      <div className="space-y-4">
        <div>
          <label className="label" htmlFor="ac-name">Name</label>
          <input id="ac-name" className="input" maxLength={60} value={form.name} placeholder="e.g. HDFC Savings" autoFocus
            onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div>
          <label className="label" htmlFor="ac-type">Type</label>
          <select id="ac-type" className="select" value={form.account_type} disabled={typeLocked}
            onChange={(e) => setForm({ ...form, account_type: e.target.value })}>
            {Object.entries(TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="ac-last4">Last 4 digits <span className="font-normal normal-case text-ink-faint">(optional)</span></label>
          <input id="ac-last4" className="input" inputMode="numeric" maxLength={4} value={form.last4} placeholder="1234"
            onChange={(e) => setForm({ ...form, last4: e.target.value.replace(/\D/g, '') })} />
          <p className="mt-1.5 text-xs text-ink-muted">Only to help you recognise it. Never enter a full account or card number.</p>
        </div>
        <div>
          <span className="label">Colour</span>
          <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Colour">
            {ACCOUNT_SWATCHES.map((c) => (
              <button key={c} type="button" onClick={() => setForm({ ...form, color: c })} aria-label={`Colour ${c}`} aria-pressed={form.color.toUpperCase() === c}
                className={`h-8 w-8 rounded-full ring-offset-2 transition ${form.color.toUpperCase() === c ? 'ring-2 ring-ink' : 'hover:scale-110'}`} style={{ background: c }} />
            ))}
          </div>
          {!editing && !form.color && <p className="mt-1.5 text-xs text-ink-muted">Left blank, a colour is picked for you.</p>}
        </div>
      </div>
    </Modal>
  )
}
