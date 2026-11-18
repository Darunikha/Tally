import { useState } from 'react'
import { Beaker, Loader2, Pencil, Play, Plus, Tags, Trash2, Wand2 } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import { Badge, Card, ConfirmDialog, EmptyState, ErrorState, InfoTip, LoadingBlock, Modal, PageHeader, Segmented } from '../components/ui'
import { useFilters } from '../context/FilterContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { formatDate, formatINR } from '../lib/format'

const SWATCHES = ['#1BAF7A', '#008300', '#EB6834', '#2A78D6', '#EDA100', '#E87BA4', '#6250D6', '#E34948', '#3F6F8F', '#8A6D3B', '#4B7F87', '#94A3B8']

function CategoryForm({ initial, onClose, onSaved }) {
  const toast = useToast()
  const [form, setForm] = useState({ name: initial?.name || '', color: initial?.color || SWATCHES[0], description: initial?.description || '' })
  const [busy, setBusy] = useState(false)
  const save = async () => {
    setBusy(true)
    try {
      if (initial) await api.patch(`/categories/${initial.id}`, form)
      else await api.post('/categories', form)
      toast.success(initial ? 'Category updated' : 'Category created')
      onSaved(); onClose()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }
  return (
    <Modal open onClose={onClose} title={initial ? 'Edit category' : 'New category'} size="sm"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!form.name.trim() || busy} onClick={save}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Save</button></>}>
      <div className="space-y-4">
        <div><label className="label" htmlFor="c-name">Name</label><input id="c-name" className="input" maxLength={40} value={form.name} disabled={initial?.name === 'Other'} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div>
          <span className="label">Colour</span>
          <div className="flex flex-wrap items-center gap-2">
            {SWATCHES.map((s) => (
              <button key={s} onClick={() => setForm({ ...form, color: s })} aria-label={`Colour ${s}`}
                className={`h-8 w-8 rounded-full ring-offset-2 transition ${form.color.toUpperCase() === s ? 'ring-2 ring-ink' : 'hover:scale-110'}`} style={{ background: s }} />
            ))}
            <label className="relative h-8 w-8 cursor-pointer overflow-hidden rounded-full ring-1 ring-line" title="Custom colour">
              <input type="color" className="absolute -inset-2 h-12 w-12 cursor-pointer" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value.toUpperCase() })} />
            </label>
          </div>
        </div>
        <div><label className="label" htmlFor="c-desc">Description</label><input id="c-desc" className="input" maxLength={200} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
      </div>
    </Modal>
  )
}

function RuleForm({ initial, categories, onClose, onSaved }) {
  const toast = useToast()
  const [form, setForm] = useState({
    rule_name: initial?.rule_name || '', regex_pattern: initial?.regex_pattern || '', category_id: initial?.category_id || categories[0]?.id || '',
    priority: initial?.priority ?? 120, applies_to: initial?.applies_to || 'debit', enabled: initial?.enabled ?? true,
  })
  const [test, setTest] = useState(null)
  const [busy, setBusy] = useState(false)
  const runTest = async () => {
    try { setTest((await api.post('/rules/test', { regex_pattern: form.regex_pattern })).data) } catch (e) { setTest({ error: errorMessage(e) }) }
  }
  const save = async () => {
    setBusy(true)
    try {
      const body = { ...form, priority: Number(form.priority) }
      if (initial) await api.patch(`/rules/${initial.id}`, body)
      else await api.post('/rules', body)
      toast.success(initial ? 'Rule updated' : 'Rule created', 'Use “Apply rules” to recategorise existing transactions.')
      onSaved(); onClose()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }
  return (
    <Modal open onClose={onClose} title={initial ? 'Edit rule' : 'New rule'} size="lg"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!form.rule_name.trim() || !form.regex_pattern.trim() || busy} onClick={save}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Save rule</button></>}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div><label className="label" htmlFor="r-name">Rule name</label><input id="r-name" className="input" maxLength={60} value={form.rule_name} onChange={(e) => setForm({ ...form, rule_name: e.target.value })} placeholder="e.g. Office canteen" /></div>
        <div><label className="label" htmlFor="r-cat">Category</label>
          <select id="r-cat" className="select" value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>{categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div className="sm:col-span-2">
          <label className="label flex items-center gap-1" htmlFor="r-rx">Pattern (regular expression)<InfoTip text="Matched case-insensitively against “MERCHANT | DESCRIPTION”. Use | for alternatives, e.g. CANTEEN|CAFETERIA. \b marks a word boundary." /></label>
          <div className="flex gap-2">
            <input id="r-rx" className="input font-mono" maxLength={300} value={form.regex_pattern} onChange={(e) => { setForm({ ...form, regex_pattern: e.target.value }); setTest(null) }} placeholder="CANTEEN|CAFETERIA" />
            <button className="btn-secondary shrink-0" disabled={!form.regex_pattern.trim()} onClick={runTest}><Beaker className="h-4 w-4" />Test</button>
          </div>
          {test && (test.error ? <p className="mt-2 text-sm text-danger-500">{test.error}</p> : (
            <div className="mt-2 rounded-xl bg-canvas p-3 text-sm">
              <p className="font-semibold text-ink">Matches {test.match_count} existing transaction{test.match_count === 1 ? '' : 's'}</p>
              <ul className="mt-1 space-y-0.5 text-xs text-ink-muted">{test.examples.slice(0, 5).map((x) => <li key={x.id} className="truncate">{formatDate(x.transaction_date)} · {x.normalized_merchant} · {formatINR(x.amount)}</li>)}</ul>
            </div>
          ))}
        </div>
        <div><label className="label flex items-center gap-1" htmlFor="r-prio">Priority<InfoTip text="Higher priority rules are checked first. Default rules use 5–100; use more than 100 to override them." /></label>
          <input id="r-prio" type="number" min={0} max={1000} className="input" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} /></div>
        <div><span className="label">Applies to</span>
          <Segmented value={form.applies_to} onChange={(v) => setForm({ ...form, applies_to: v })} options={[{ value: 'debit', label: 'Debits' }, { value: 'credit', label: 'Credits' }, { value: 'any', label: 'Both' }]} /></div>
        <label className="flex items-center gap-2 text-sm text-ink-soft sm:col-span-2"><input type="checkbox" className="accent-brand-500" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />Rule enabled</label>
      </div>
    </Modal>
  )
}

function Toggle({ checked, onChange, label }) {
  return (
    <button role="switch" aria-checked={checked} aria-label={label} onClick={onChange}
      className={`relative h-6 w-11 shrink-0 rounded-full transition ${checked ? 'bg-brand-solid' : 'bg-line'}`}>
      <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-surface shadow transition-all ${checked ? 'left-[1.375rem]' : 'left-0.5'}`} />
    </button>
  )
}

export default function CategoriesRules() {
  const toast = useToast()
  const { dataChanged } = useFilters()
  const [tab, setTab] = useState('categories')
  const cats = useApi('/categories')
  const rules = useApi('/rules')
  const [catForm, setCatForm] = useState(null)
  const [ruleForm, setRuleForm] = useState(null)
  const [del, setDel] = useState(null)
  const [busy, setBusy] = useState(false)
  const [q, setQ] = useState('')

  const refresh = () => { cats.reload(); rules.reload() }

  const applyRules = async () => {
    setBusy(true)
    try {
      const r = await api.post('/rules/apply')
      toast.success(`${r.data.recategorized} transaction(s) changed category. Manual choices were kept.`, 'Rules applied')
      refresh(); dataChanged()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }

  const toggleRule = async (r) => {
    try { await api.patch(`/rules/${r.id}`, { enabled: !r.enabled }); rules.setData((rs) => rs.map((x) => (x.id === r.id ? { ...x, enabled: !x.enabled } : x))) } catch (e) { toast.error(errorMessage(e)) }
  }

  const doDelete = async () => {
    setBusy(true)
    try {
      if (del.kind === 'category') {
        const r = await api.delete(`/categories/${del.item.id}`)
        toast.success(`Category deleted. ${r.data.moved_transactions} transaction(s) moved to Other.`)
        dataChanged()
      } else {
        await api.delete(`/rules/${del.item.id}`)
        toast.success('Rule deleted')
      }
      setDel(null); refresh()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }

  const filteredRules = (rules.data || []).filter((r) => !q || `${r.rule_name} ${r.regex_pattern} ${r.category_name}`.toLowerCase().includes(q.toLowerCase()))

  return (
    <div className="animate-fade-up">
      <PageHeader title="Categories & Rules" subtitle="Control how transactions are categorised. Manual changes always win over rules."
        actions={<>
          <button className="btn-secondary" onClick={applyRules} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}Apply rules</button>
          <button className="btn-primary" onClick={() => (tab === 'categories' ? setCatForm({}) : setRuleForm({}))}><Plus className="h-4 w-4" />New {tab === 'categories' ? 'category' : 'rule'}</button>
        </>} />

      <div className="mb-5"><Segmented value={tab} onChange={setTab} options={[{ value: 'categories', label: `Categories${cats.data ? ` (${cats.data.length})` : ''}` }, { value: 'rules', label: `Rules${rules.data ? ` (${rules.data.length})` : ''}` }]} /></div>

      {tab === 'categories' ? (
        cats.error ? <Card className="card-pad"><ErrorState message={cats.error} onRetry={cats.reload} /></Card> : !cats.data ? <Card className="card-pad"><LoadingBlock rows={6} /></Card> : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {cats.data.map((c) => (
              <Card key={c.id} className="flex items-start gap-3 p-4">
                <span className="mt-0.5 grid h-10 w-10 shrink-0 place-items-center rounded-xl" style={{ background: `${c.color}22` }}><Tags className="h-5 w-5" style={{ color: c.color }} /></span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2"><p className="truncate font-bold text-ink">{c.name}</p>{!c.is_default && <Badge tone="navy">Custom</Badge>}</div>
                  <p className="truncate text-xs text-ink-muted">{c.description || '—'}</p>
                  <p className="mt-1 text-xs text-ink-soft">{c.transaction_count} transaction{c.transaction_count === 1 ? "" : "s"} · {c.rule_count} rule{c.rule_count === 1 ? "" : "s"}</p>
                  {c.excluded_from_totals && <p className="mt-1 text-xs text-ink-muted">Once you add a credit card statement, these are left out of income and spending so nothing is counted twice.</p>}
                </div>
                <div className="flex gap-1">
                  <button className="rounded-lg p-1.5 max-sm:p-2.5 text-ink-muted hover:bg-canvas hover:text-ink" onClick={() => setCatForm(c)} aria-label={`Edit ${c.name}`}><Pencil className="h-4 w-4" /></button>
                  {c.name !== 'Other' && !c.excluded_from_totals && <button className="rounded-lg p-1.5 max-sm:p-2.5 text-ink-muted hover:bg-danger-50 hover:text-danger-500" onClick={() => setDel({ kind: 'category', item: c })} aria-label={`Delete ${c.name}`}><Trash2 className="h-4 w-4" /></button>}
                </div>
              </Card>
            ))}
          </div>
        )
      ) : (
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-3 p-4">
            <input className="input max-w-xs" placeholder="Search rules…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search rules" />
            <p className="text-xs text-ink-muted">Rules are checked from highest to lowest priority; the first match wins.</p>
          </div>
          {rules.error ? <ErrorState message={rules.error} onRetry={rules.reload} /> : !rules.data ? <div className="p-5"><LoadingBlock rows={8} /></div> : filteredRules.length === 0 ? <EmptyState compact icon={Wand2} title="No rules found" /> : (
            <div className="scrollbar-thin overflow-x-auto">
              <table className="w-full min-w-[820px]">
                <thead className="bg-canvas/70"><tr>
                  <th className="table-th">On</th><th className="table-th">Rule</th><th className="table-th">Pattern</th><th className="table-th">Category</th>
                  <th className="table-th text-right">Priority</th><th className="table-th">Applies to</th><th className="table-th text-right">Matches</th><th className="table-th" />
                </tr></thead>
                <tbody className="divide-y divide-line">
                  {filteredRules.map((r) => (
                    <tr key={r.id} className={r.enabled ? '' : 'opacity-50'}>
                      <td className="table-td"><Toggle checked={r.enabled} onChange={() => toggleRule(r)} label={`Toggle ${r.rule_name}`} /></td>
                      <td className="table-td"><p className="font-semibold text-ink">{r.rule_name}</p>{!r.is_default && <Badge tone="navy">Custom</Badge>}</td>
                      <td className="table-td max-w-[18rem]"><code className="block truncate rounded bg-canvas px-1.5 py-0.5 font-mono text-xs text-ink-soft" title={r.regex_pattern}>{r.regex_pattern}</code></td>
                      <td className="table-td"><span className="inline-flex items-center gap-1.5 text-sm"><span className="h-2 w-2 rounded-full" style={{ background: r.category_color }} />{r.category_name}</span></td>
                      <td className="table-td text-right font-semibold">{r.priority}</td>
                      <td className="table-td capitalize text-ink-soft">{r.applies_to === 'any' ? 'Both' : `${r.applies_to}s`}</td>
                      <td className="table-td text-right text-ink-soft">{r.match_count}</td>
                      <td className="table-td"><div className="flex justify-end gap-1">
                        <button className="rounded-lg p-1.5 max-sm:p-2.5 text-ink-muted hover:bg-canvas hover:text-ink" onClick={() => setRuleForm(r)} aria-label="Edit rule"><Pencil className="h-4 w-4" /></button>
                        <button className="rounded-lg p-1.5 max-sm:p-2.5 text-ink-muted hover:bg-danger-50 hover:text-danger-500" onClick={() => setDel({ kind: 'rule', item: r })} aria-label="Delete rule"><Trash2 className="h-4 w-4" /></button>
                      </div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {catForm && <CategoryForm initial={catForm.id ? catForm : null} onClose={() => setCatForm(null)} onSaved={() => { refresh(); dataChanged() }} />}
      {ruleForm && cats.data && <RuleForm initial={ruleForm.id ? ruleForm : null} categories={cats.data} onClose={() => setRuleForm(null)} onSaved={refresh} />}
      <ConfirmDialog open={!!del} busy={busy} danger onClose={() => setDel(null)} onConfirm={doDelete}
        title={del?.kind === 'category' ? `Delete “${del?.item.name}”?` : `Delete rule “${del?.item.rule_name}”?`} confirmLabel="Delete"
        message={del?.kind === 'category'
          ? `${del?.item.transaction_count} transaction(s) will move to Other (flagged for review) and ${del?.item.rule_count} rule(s) using this category will be deleted.`
          : 'Transactions already categorised by this rule keep their category until you apply rules again.'} />
    </div>
  )
}
