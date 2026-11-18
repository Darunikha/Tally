import { useState } from 'react'
import { ChevronLeft, ChevronRight, Loader2, Pencil, PiggyBank, Plus, Trash2 } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import { BudgetBar, STATUS, remainingText } from '../components/BudgetProgress'
import { useCategories } from '../components/TransactionDetail'
import { Badge, Card, CardHeader, ConfirmDialog, EmptyState, ErrorState, LoadingBlock, Modal, PageHeader } from '../components/ui'
import { useFilters } from '../context/FilterContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { formatINR } from '../lib/format'

const THRESHOLDS = [50, 60, 70, 80, 90, 100]
const OVERALL = 'overall'

function BudgetForm({ initial, preset, categories, hasOverall, onClose, onSaved }) {
  const toast = useToast()
  const editing = !!initial
  const choices = editing ? [] : [
    ...(hasOverall ? [] : [{ id: OVERALL, name: 'Overall spending (all categories)' }]),
    ...categories.filter((c) => c.name !== 'Income' && !preset?.taken.has(c.id)),
  ]
  const [picked, setPicked] = useState(editing ? (initial.category_id || OVERALL) : preset?.category_id)
  const target = editing || choices.some((c) => c.id === picked) ? picked : (choices[0]?.id || '')
  const [limit, setLimit] = useState(editing ? String(initial.monthly_limit) : (preset?.limit ? String(preset.limit) : ''))
  const [threshold, setThreshold] = useState(initial?.alert_threshold ?? 80)
  const [busy, setBusy] = useState(false)
  const amount = Number(limit)
  const valid = target && Number.isFinite(amount) && amount > 0 && amount <= 100_000_000

  const save = async () => {
    setBusy(true)
    try {
      await api.put('/budgets', { category_id: target === OVERALL ? null : target, monthly_limit: amount, alert_threshold: threshold })
      toast.success(editing ? 'Budget updated' : 'Budget created')
      onSaved(); onClose()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }

  return (
    <Modal open onClose={onClose} title={editing ? `Edit budget · ${initial.name}` : 'New budget'} size="sm"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={!valid || busy} onClick={save}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Save budget</button></>}>
      <div className="space-y-4">
        {!editing && (
          <div>
            <label className="label" htmlFor="b-cat">Category</label>
            <select id="b-cat" className="select" value={target} onChange={(e) => setPicked(e.target.value)}>
              {choices.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
        )}
        <div>
          <label className="label" htmlFor="b-limit">Monthly limit (₹)</label>
          <input id="b-limit" className="input" type="number" inputMode="decimal" min="1" max="100000000" step="any" value={limit}
            onChange={(e) => setLimit(e.target.value)} placeholder="e.g. 8000" autoFocus />
          {preset?.hint && <p className="mt-1.5 text-xs text-ink-muted">{preset.hint}</p>}
        </div>
        <div>
          <label className="label" htmlFor="b-alert">Warn me at</label>
          <select id="b-alert" className="select" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))}>
            {THRESHOLDS.map((t) => <option key={t} value={t}>{t}% of the limit</option>)}
          </select>
        </div>
      </div>
    </Modal>
  )
}

function BudgetCard({ b, large = false, onEdit, onDelete }) {
  const s = STATUS[b.status]
  return (
    <Card className="card-pad">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className={`flex items-center gap-2 font-bold text-ink ${large ? 'text-lg' : 'text-base'}`}>
            <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: b.color }} aria-hidden="true" />
            <span className="truncate">{b.name}</span>
          </h3>
          <p className="mt-0.5 text-xs text-ink-muted">Warns at {b.alert_threshold}%</p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Badge tone={s.tone}>{s.label}</Badge>
          <button className="rounded-lg p-1.5 max-sm:p-2.5 text-ink-muted hover:bg-canvas hover:text-ink" onClick={() => onEdit(b)} aria-label={`Edit ${b.name} budget`}><Pencil className="h-4 w-4" /></button>
          <button className="rounded-lg p-1.5 max-sm:p-2.5 text-ink-muted hover:bg-danger-50 hover:text-danger-600" onClick={() => onDelete(b)} aria-label={`Delete ${b.name} budget`}><Trash2 className="h-4 w-4" /></button>
        </div>
      </div>

      <p className={`mt-4 font-extrabold tracking-tight text-ink ${large ? 'text-3xl' : 'text-2xl'}`}>
        {formatINR(b.spent)} <span className="text-sm font-semibold text-ink-muted">of {formatINR(b.monthly_limit)}</span>
      </p>
      <div className="mt-3"><BudgetBar budget={b} /></div>
      <div className="mt-2 flex flex-wrap justify-between gap-x-4 text-sm">
        <span className="text-ink-muted">{Math.round(b.percent)}% used</span>
        <span className={b.status === 'over' ? 'font-semibold text-danger-600' : 'font-semibold text-ink'}>{remainingText(b)}</span>
      </div>
      {(b.daily_allowance != null || b.projected_over) && (
        <ul className="mt-3 space-y-1 border-t border-line pt-3 text-xs text-ink-muted">
          {b.daily_allowance != null && <li>You can spend about <b className="text-ink">{formatINR(b.daily_allowance)}</b> a day for the rest of the month.</li>}
          {b.projected_over && b.status !== 'over' && (
            <li className="font-semibold text-warn-500">At this pace you'll spend about {formatINR(b.projected)}, which is {formatINR(b.projected - b.monthly_limit)} over.</li>
          )}
        </ul>
      )}
    </Card>
  )
}

export default function Budgets() {
  const toast = useToast()
  const { version, dataChanged, periods, ready } = useFilters()
  const now = new Date()
  const thisMonth = { year: now.getFullYear(), month: now.getMonth() + 1 }
  // start on the latest month that has data, so a user with older statements doesn't land on an empty page
  const [picked, setPicked] = useState(null)
  const ym = picked || (periods.latest ? { year: periods.latest.year, month: periods.latest.month } : thisMonth)
  const { data, loading, error, reload } = useApi(ready ? '/budgets/status' : null, ym, [version])
  const categories = useCategories([version])
  const [form, setForm] = useState(null) // { initial?, preset? }
  const [removing, setRemoving] = useState(null)
  const [busy, setBusy] = useState(false)

  const shift = (d) => setPicked(() => {
    const idx = ym.year * 12 + (ym.month - 1) + d
    return { year: Math.floor(idx / 12), month: (idx % 12) + 1 }
  })
  const isNow = ym.year * 12 + ym.month >= thisMonth.year * 12 + thisMonth.month
  const taken = new Set((data?.budgets || []).map((b) => b.category_id))
  const hasAny = !!data && (data.overall || data.budgets.length > 0)

  const remove = async () => {
    setBusy(true)
    try {
      await api.delete(`/budgets/${removing.id}`)
      toast.success('Budget deleted')
      setRemoving(null); reload(); dataChanged()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }
  const saved = () => { reload(); dataChanged() }
  const openNew = (preset) => setForm({ preset: { ...preset, taken } })

  return (
    <div className="animate-fade-up">
      <PageHeader title="Budgets" subtitle="Set monthly limits and see how you're tracking against them."
        actions={<>
          <div className="flex items-center rounded-xl border border-line bg-surface shadow-sm">
            <button className="rounded-l-xl p-2.5 text-ink-soft hover:bg-canvas" onClick={() => shift(-1)} aria-label="Previous month"><ChevronLeft className="h-4 w-4" /></button>
            <span className="min-w-[8.5rem] text-center text-sm font-semibold text-ink" aria-live="polite">{data?.month.label || '…'}</span>
            <button className="rounded-r-xl p-2.5 text-ink-soft hover:bg-canvas disabled:opacity-40" onClick={() => shift(1)} disabled={isNow} aria-label="Next month"><ChevronRight className="h-4 w-4" /></button>
          </div>
          <button className="btn-primary" onClick={() => openNew()}><Plus className="h-4 w-4" />Add budget</button>
        </>} />

      {error ? <Card className="card-pad"><ErrorState message={error} onRetry={reload} /></Card> : loading && !data ? (
        <Card className="card-pad"><LoadingBlock rows={5} /></Card>
      ) : (
        <>
          {data.month.is_current && hasAny && (
            <p className="mb-4 text-sm text-ink-muted">{data.month.days_left} day{data.month.days_left === 1 ? '' : 's'} left in {data.month.label}.</p>
          )}

          {!hasAny ? (
            <Card className="card-pad">
              <EmptyState icon={PiggyBank} title="No budgets yet"
                message="Pick a category you want to keep in check, or set one limit for everything, and Tally will show how you're tracking all month."
                action={<div className="flex flex-wrap justify-center gap-2">
                  <button className="btn-primary" onClick={() => openNew({ category_id: OVERALL, limit: data.suggested_overall, hint: data.suggested_overall ? `Suggested from your average monthly spending: ${formatINR(data.suggested_overall)}.` : undefined })}>
                    <Plus className="h-4 w-4" />Set an overall budget</button>
                  <button className="btn-secondary" onClick={() => openNew()}>Budget a category</button>
                </div>} />
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              {data.overall ? (
                <div className="md:col-span-2"><BudgetCard b={data.overall} large onEdit={(b) => setForm({ initial: b })} onDelete={setRemoving} /></div>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-dashed border-line bg-surface/60 px-5 py-4 md:col-span-2">
                  <p className="text-sm text-ink-soft"><b className="text-ink">Overall budget.</b> Cap your total monthly spending across every category.</p>
                  <button className="btn-secondary btn-sm" onClick={() => openNew({ category_id: OVERALL, limit: data.suggested_overall, hint: data.suggested_overall ? `Suggested from your average monthly spending: ${formatINR(data.suggested_overall)}.` : undefined })}>Set overall budget</button>
                </div>
              )}
              {data.budgets.map((b) => <BudgetCard key={b.id} b={b} onEdit={(x) => setForm({ initial: x })} onDelete={setRemoving} />)}
            </div>
          )}

          {data.unbudgeted.length > 0 && (
            <Card className="card-pad mt-6">
              <CardHeader icon={PiggyBank} title="Spending without a budget" subtitle={`Where your money went in ${data.month.label}`} />
              <ul className="divide-y divide-line">
                {data.unbudgeted.map((u) => (
                  <li key={u.category_id} className="flex items-center gap-3 py-3">
                    <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: u.color }} aria-hidden="true" />
                    <span className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">{u.name}</span>
                    <span className="text-sm font-bold text-ink">{formatINR(u.spent)}</span>
                    <button className="btn-secondary btn-sm" aria-label={`Set a budget for ${u.name}`}
                      onClick={() => openNew({ category_id: u.category_id, limit: u.suggested_limit, hint: `Suggested ${formatINR(u.suggested_limit)}, based on your recent spending.` })}>Set budget</button>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}

      {form && <BudgetForm initial={form.initial} preset={form.preset} categories={categories} hasOverall={!!data?.overall} onClose={() => setForm(null)} onSaved={saved} />}
      <ConfirmDialog open={!!removing} title="Delete this budget?" danger confirmLabel="Delete budget" busy={busy} onConfirm={remove} onClose={() => setRemoving(null)}
        message={removing ? `The ${removing.name} budget of ${formatINR(removing.monthly_limit)} will be removed. Your transactions are not affected.` : ''} />
    </div>
  )
}
