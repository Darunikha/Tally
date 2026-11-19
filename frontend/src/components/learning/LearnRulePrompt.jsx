import { useState } from 'react'
import { Loader2, Wand2 } from 'lucide-react'
import { api, errorMessage } from '../../api/client'
import { useToast } from '../../context/ToastContext'
import { Modal, Segmented } from '../ui'

const SCOPES = [{ value: 'debit', label: 'Debits' }, { value: 'credit', label: 'Credits' }, { value: 'any', label: 'Both' }]

/** Shown right after a category correction: offers to make it a rule so Tally does it from now on. */
export default function LearnRulePrompt({ offer, onDone, onClose }) {
  const toast = useToast()
  const [scope, setScope] = useState(offer.applies_to)
  const [busy, setBusy] = useState(false)
  const { merchant, category_id: categoryId, category_name: category, similar_count: similar } = offer

  const create = async () => {
    setBusy(true)
    try {
      const r = (await api.post('/rules/learn', { merchant, category_id: categoryId, applies_to: scope })).data
      const n = r.recategorized
      toast.success(n ? `${n.toLocaleString('en-IN')} transaction${n === 1 ? '' : 's'} moved to ${category}.` : `Future ${merchant} transactions will go to ${category}.`, 'Rule created')
      onDone?.()
      onClose()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }

  return (
    <Modal open onClose={onClose} title="Remember this?" size="sm"
      footer={<><button className="btn-secondary" onClick={onClose} disabled={busy}>Not now</button>
        <button className="btn-primary" onClick={create} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}Create rule</button></>}>
      <p className="text-sm text-ink-soft">
        Always file <b className="text-ink">{merchant}</b> under <b className="text-ink">{category}</b>?
      </p>
      <p className="mt-2 text-sm text-ink-muted">
        {similar > 0
          ? `${similar.toLocaleString('en-IN')} other ${merchant} transaction${similar === 1 ? '' : 's'} will move too, and future statements will follow it.`
          : 'Future statements will follow it automatically.'}
        {' '}Anything you have set by hand stays as you left it.
      </p>
      <div className="mt-4">
        <span className="label">Applies to</span>
        <Segmented size="sm" value={scope} onChange={setScope} options={SCOPES} />
      </div>
      <p className="mt-3 text-xs text-ink-muted">You can edit or delete the rule any time in Categories &amp; Rules.</p>
    </Modal>
  )
}
