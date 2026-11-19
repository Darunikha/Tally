import { useState } from 'react'
import { Loader2, Sparkles, Wand2 } from 'lucide-react'
import { api, errorMessage } from '../../api/client'
import { useToast } from '../../context/ToastContext'
import { useApi } from '../../hooks/useApi'
import { formatINR } from '../../lib/format'
import { MerchantAvatar } from '../TransactionDetail'
import { Card, CardHeader, CategoryPill } from '../ui'

const SCOPE_NOTE = { debit: 'payments', credit: 'money received', any: 'payments and receipts' }

async function learn(toast, { merchant, category_id, applies_to }, categoryName) {
  const r = (await api.post('/rules/learn', { merchant, category_id, applies_to })).data
  const n = r.recategorized
  toast.success(n ? `${n.toLocaleString('en-IN')} transaction${n === 1 ? '' : 's'} moved to ${categoryName}.` : `Future ${merchant} transactions will go to ${categoryName}.`, 'Rule created')
}

/** Merchants you keep moving to the same category, offered as rules. Renders nothing when there is nothing to offer. */
export function SuggestedRules({ version, onChanged }) {
  const toast = useToast()
  const { data, reload } = useApi('/categories/suggestions', undefined, [version])
  const [busy, setBusy] = useState('')
  if (!data?.length) return null

  const accept = async (s) => {
    setBusy(s.merchant)
    try { await learn(toast, s, s.category_name); reload(); onChanged?.() } catch (e) { toast.error(errorMessage(e)) } finally { setBusy('') }
  }
  const dismiss = async (s) => {
    setBusy(s.merchant)
    try { await api.post('/categories/suggestions/dismiss', { merchant: s.merchant, category_id: s.category_id }); reload() } catch (e) { toast.error(errorMessage(e)) } finally { setBusy('') }
  }

  return (
    <Card className="card-pad mb-6 border-brand-200">
      <CardHeader icon={Sparkles} title="Tally noticed a pattern" subtitle="You keep moving these to the same category. Make it a rule and Tally does it for you." />
      <ul className="divide-y divide-line" aria-label="Suggested rules">
        {data.map((s) => (
          <li key={`${s.merchant}|${s.category_id}`} className="flex flex-wrap items-center gap-x-4 gap-y-3 py-3">
            <MerchantAvatar name={s.merchant} color={s.category_color} />
            <div className="min-w-0 flex-1 basis-56">
              <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">{s.merchant}<span aria-hidden="true" className="text-ink-faint">→</span><CategoryPill name={s.category_name} color={s.category_color} /></p>
              <p className="mt-0.5 text-xs text-ink-muted">
                You moved it there {s.evidence} times
                {s.affected > 0 ? <> · would also move {s.affected.toLocaleString('en-IN')} other transaction{s.affected === 1 ? '' : 's'}</> : ''}
                {s.applies_to !== 'any' ? <> · {SCOPE_NOTE[s.applies_to]} only</> : null}
              </p>
            </div>
            <div className="flex gap-2">
              <button className="btn-ghost btn-sm" onClick={() => dismiss(s)} disabled={busy === s.merchant} aria-label={`Not now for ${s.merchant}`}>Not now</button>
              <button className="btn-primary btn-sm" onClick={() => accept(s)} disabled={busy === s.merchant} aria-label={`Create a rule for ${s.merchant}`}>
                {busy === s.merchant ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wand2 className="h-3.5 w-3.5" />}Create rule
              </button>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

/** Payees Tally could not place, grouped so one choice sorts all of a merchant's transactions and is remembered. */
export function UncategorisedMerchants({ categories, version, onChanged }) {
  const toast = useToast()
  const { data, reload } = useApi('/categories/uncategorised', undefined, [version])
  const [choice, setChoice] = useState({})
  const [busy, setBusy] = useState('')
  if (!data?.length) return null
  const options = (categories || []).filter((c) => c.name !== 'Other')

  const apply = async (row) => {
    const cat = options.find((c) => c.id === choice[row.merchant])
    setBusy(row.merchant)
    try { await learn(toast, { merchant: row.merchant, category_id: cat.id, applies_to: row.applies_to }, cat.name); reload(); onChanged?.() } catch (e) { toast.error(errorMessage(e)) } finally { setBusy('') }
  }

  return (
    <Card className="card-pad mb-6">
      <CardHeader icon={Wand2} title="Needs a category" subtitle="Tally could not place these. Pick a category once and it is remembered for next time." />
      <ul className="divide-y divide-line" aria-label="Merchants that need a category">
        {data.map((r, i) => (
          <li key={r.merchant} className="flex flex-wrap items-center gap-x-4 gap-y-3 py-3">
            <MerchantAvatar name={r.merchant} />
            <div className="min-w-0 flex-1 basis-56">
              <p className="text-sm font-semibold text-ink">{r.merchant}</p>
              <p className="text-xs text-ink-muted">{r.count} transaction{r.count === 1 ? '' : 's'} · {formatINR(r.total)}</p>
              {r.sample && <p className="truncate text-xs text-ink-faint" title={r.sample}>{r.sample}</p>}
            </div>
            <label className="sr-only" htmlFor={`pick-merchant-${i}`}>Category for {r.merchant}</label>
            <select id={`pick-merchant-${i}`} className="select w-auto min-w-[11rem]" value={choice[r.merchant] || ''}
              onChange={(e) => setChoice({ ...choice, [r.merchant]: e.target.value })}>
              <option value="">Choose a category…</option>
              {options.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <button className="btn-primary btn-sm" disabled={!choice[r.merchant] || busy === r.merchant} onClick={() => apply(r)} aria-label={`Apply to all ${r.merchant} transactions`}>
              {busy === r.merchant && <Loader2 className="h-3.5 w-3.5 animate-spin" />}Apply to all
            </button>
          </li>
        ))}
      </ul>
    </Card>
  )
}
