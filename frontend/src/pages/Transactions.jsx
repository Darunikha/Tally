import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ArrowDown, ArrowUp, ArrowUpDown, Download, Filter, ListX, Loader2, Search, StickyNote, Tag, X } from 'lucide-react'
import { api, cleanParams, errorMessage } from '../api/client'
import TransactionDetail, { MerchantAvatar, useCategories } from '../components/TransactionDetail'
import { Badge, Card, CategoryPill, EmptyState, ErrorState, LoadingBlock, PageHeader, Pagination, TypeBadge } from '../components/ui'
import { useFilters } from '../context/FilterContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { formatDate, formatINR } from '../lib/format'

const FILTER_KEYS = ['search', 'start', 'end', 'category_id', 'type', 'payment_method', 'upload_id', 'needs_review', 'merchant']

export default function Transactions() {
  const toast = useToast()
  const [sp, setSp] = useSearchParams()
  const { statements, version, dataChanged } = useFilters()
  const categories = useCategories([version])
  const methods = useApi('/transactions/payment-methods')
  const [selected, setSelected] = useState(null)
  const [checked, setChecked] = useState(new Set())
  const [bulkCat, setBulkCat] = useState('')
  const [busy, setBusy] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [searchDraft, setSearchDraft] = useState(sp.get('search') || '')

  const f = Object.fromEntries(FILTER_KEYS.map((k) => [k, sp.get(k) || '']))
  const sort = sp.get('sort') || 'date'
  const order = sp.get('order') || 'desc'
  const page = Number(sp.get('page') || 1)
  const pageSize = Number(sp.get('page_size') || 25)

  useEffect(() => { setSearchDraft(sp.get('search') || '') }, [sp])

  const params = useMemo(() => cleanParams({ ...f, sort, order, page, page_size: pageSize }), [sp]) // eslint-disable-line react-hooks/exhaustive-deps
  const { data, loading, error, reload } = useApi('/transactions', params, [version])

  const update = (patch, resetPage = true) => {
    const next = new URLSearchParams(sp)
    Object.entries(patch).forEach(([k, v]) => (v === '' || v == null ? next.delete(k) : next.set(k, String(v))))
    if (resetPage && !('page' in patch)) next.delete('page')
    setSp(next)
    setChecked(new Set())
  }

  // debounce search typing
  useEffect(() => {
    const t = setTimeout(() => { if ((sp.get('search') || '') !== searchDraft.trim()) update({ search: searchDraft.trim() }) }, 350)
    return () => clearTimeout(t)
  }, [searchDraft]) // eslint-disable-line react-hooks/exhaustive-deps

  const activeCount = FILTER_KEYS.filter((k) => k !== 'search' && f[k]).length
  const toggleSort = (key) => update({ sort: key, order: sort === key && order === 'desc' ? 'asc' : 'desc' }, false)
  const SortIcon = ({ k }) => (sort !== k ? <ArrowUpDown className="h-3.5 w-3.5 opacity-40" /> : order === 'desc' ? <ArrowDown className="h-3.5 w-3.5" /> : <ArrowUp className="h-3.5 w-3.5" />)

  const allChecked = data?.items.length > 0 && data.items.every((t) => checked.has(t.id))
  const toggleAll = () => setChecked(allChecked ? new Set() : new Set(data.items.map((t) => t.id)))
  const toggle = (id) => setChecked((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })

  const applyBulk = async () => {
    setBusy(true)
    try {
      const r = await api.post('/transactions/bulk-category', { transaction_ids: [...checked], category_id: bulkCat })
      toast.success(`${r.data.updated} transactions recategorised`)
      setChecked(new Set()); setBulkCat('')
      dataChanged()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }

  const exportCsv = async () => {
    try {
      const r = await api.get('/transactions/export', { params: cleanParams(f), responseType: 'blob' })
      const url = URL.createObjectURL(r.data)
      const a = document.createElement('a')
      a.href = url; a.download = 'tally-transactions.csv'; a.click()
      URL.revokeObjectURL(url)
    } catch (e) { toast.error(errorMessage(e, 'Export failed')) }
  }

  const catName = (id) => categories.find((c) => c.id === id)?.name
  const chips = [
    f.category_id && ['category_id', `Category: ${catName(f.category_id) || '…'}`],
    f.type && ['type', f.type === 'debit' ? 'Debits' : 'Credits'],
    f.payment_method && ['payment_method', f.payment_method],
    f.start && ['start', `From ${formatDate(f.start)}`],
    f.end && ['end', `To ${formatDate(f.end)}`],
    f.upload_id && ['upload_id', `Statement: ${statements.find((s) => s.id === f.upload_id)?.file_name || '…'}`],
    f.needs_review && ['needs_review', 'Needs review'],
    f.merchant && ['merchant', `Merchant: ${f.merchant}`],
  ].filter(Boolean)

  return (
    <div className="animate-fade-up">
      <PageHeader title="Transactions" subtitle={data ? `${data.total.toLocaleString('en-IN')} transactions` : 'All imported transactions'}
        actions={<button className="btn-secondary" onClick={exportCsv}><Download className="h-4 w-4" />Export CSV</button>} />

      <Card className="mb-4 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <label className="relative min-w-[14rem] flex-1">
            <span className="sr-only">Search</span>
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
            <input className="input pl-10" placeholder="Search merchant, description, UPI ID, notes…" value={searchDraft} maxLength={100} onChange={(e) => setSearchDraft(e.target.value)} />
          </label>
          <select className="select w-auto min-w-[9rem]" aria-label="Type" value={f.type} onChange={(e) => update({ type: e.target.value })}>
            <option value="">All types</option><option value="debit">Debits</option><option value="credit">Credits</option>
          </select>
          <select className="select w-auto min-w-[11rem]" aria-label="Category" value={f.category_id} onChange={(e) => update({ category_id: e.target.value })}>
            <option value="">All categories</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <button className={`btn-secondary ${activeCount ? 'ring-2 ring-brand-200' : ''}`} onClick={() => setShowFilters((s) => !s)} aria-expanded={showFilters}>
            <Filter className="h-4 w-4" />More filters{activeCount > 0 && <span className="rounded-full bg-brand-500 px-1.5 text-xs text-white">{activeCount}</span>}
          </button>
        </div>
        {showFilters && (
          <div className="mt-4 grid grid-cols-1 gap-3 border-t border-line pt-4 sm:grid-cols-2 lg:grid-cols-5">
            <div><label className="label" htmlFor="f-start">From</label><input id="f-start" type="date" className="input" value={f.start} onChange={(e) => update({ start: e.target.value })} /></div>
            <div><label className="label" htmlFor="f-end">To</label><input id="f-end" type="date" className="input" value={f.end} min={f.start || undefined} onChange={(e) => update({ end: e.target.value })} /></div>
            <div><label className="label" htmlFor="f-pm">Payment method</label>
              <select id="f-pm" className="select" value={f.payment_method} onChange={(e) => update({ payment_method: e.target.value })}>
                <option value="">All methods</option>{(methods.data || []).map((m) => <option key={m}>{m}</option>)}
              </select></div>
            <div><label className="label" htmlFor="f-st">Statement</label>
              <select id="f-st" className="select" value={f.upload_id} onChange={(e) => update({ upload_id: e.target.value })}>
                <option value="">All statements</option>{statements.map((s) => <option key={s.id} value={s.id}>{s.bank_name} · {s.file_name}</option>)}
              </select></div>
            <div><label className="label" htmlFor="f-rev">Review</label>
              <select id="f-rev" className="select" value={f.needs_review} onChange={(e) => update({ needs_review: e.target.value })}>
                <option value="">All</option><option value="true">Needs review only</option>
              </select></div>
          </div>
        )}
        {chips.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {chips.map(([k, l]) => (
              <button key={k} onClick={() => update({ [k]: '' })} className="chip bg-brand-50 text-brand-700 hover:bg-brand-100">{l}<X className="h-3 w-3" /></button>
            ))}
            <button className="text-xs font-semibold text-ink-muted hover:text-ink" onClick={() => setSp(new URLSearchParams())}>Clear all</button>
          </div>
        )}
      </Card>

      {checked.size > 0 && (
        <Card className="mb-4 flex flex-wrap items-center gap-3 border-brand-200 bg-brand-50/60 p-3 animate-fade-up">
          <Tag className="h-4 w-4 text-brand-600" />
          <span className="text-sm font-semibold text-ink">{checked.size} selected</span>
          <select className="select w-auto min-w-[12rem]" aria-label="New category" value={bulkCat} onChange={(e) => setBulkCat(e.target.value)}>
            <option value="">Move to category…</option>{categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <button className="btn-primary btn-sm" disabled={!bulkCat || busy} onClick={applyBulk}>{busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}Apply</button>
          <button className="btn-ghost btn-sm ml-auto" onClick={() => setChecked(new Set())}>Clear selection</button>
        </Card>
      )}

      <Card className="overflow-hidden">
        {error ? <ErrorState message={error} onRetry={reload} /> : loading && !data ? <div className="p-6"><LoadingBlock rows={10} /></div> : data.items.length === 0 ? (
          <EmptyState icon={ListX} title="No transactions found" message={chips.length || f.search ? 'Try removing some filters.' : 'Upload a statement to get started.'} />
        ) : (
          <>
            {/* desktop table */}
            <div className={`scrollbar-thin hidden overflow-x-auto md:block ${loading ? 'opacity-60' : ''}`}>
              <table className="w-full">
                <thead className="bg-canvas/70"><tr>
                  <th className="table-th w-10"><input type="checkbox" className="accent-brand-500" checked={allChecked} onChange={toggleAll} aria-label="Select all on page" /></th>
                  <th className="table-th"><button className="inline-flex items-center gap-1" onClick={() => toggleSort('date')}>Date<SortIcon k="date" /></button></th>
                  <th className="table-th"><button className="inline-flex items-center gap-1" onClick={() => toggleSort('merchant')}>Merchant<SortIcon k="merchant" /></button></th>
                  <th className="table-th">Category</th>
                  <th className="table-th">Method</th>
                  <th className="table-th hidden xl:table-cell">UPI ID</th>
                  <th className="table-th hidden 2xl:table-cell">Account</th>
                  <th className="table-th text-right"><button className="inline-flex items-center gap-1" onClick={() => toggleSort('amount')}>Amount<SortIcon k="amount" /></button></th>
                  <th className="table-th">Type</th>
                </tr></thead>
                <tbody className="divide-y divide-line">
                  {data.items.map((t) => (
                    <tr key={t.id} className={`cursor-pointer transition hover:bg-canvas/60 ${checked.has(t.id) ? 'bg-brand-50/50' : ''}`} onClick={() => setSelected(t)}>
                      <td className="table-td" onClick={(e) => e.stopPropagation()}><input type="checkbox" className="accent-brand-500" checked={checked.has(t.id)} onChange={() => toggle(t.id)} aria-label={`Select ${t.normalized_merchant}`} /></td>
                      <td className="table-td whitespace-nowrap text-ink-soft">{formatDate(t.transaction_date)}</td>
                      <td className="table-td max-w-[20rem]">
                        <div className="flex items-center gap-3">
                          <MerchantAvatar name={t.normalized_merchant} color={t.category_color} size="sm" />
                          <div className="min-w-0">
                            <p className="flex items-center gap-1.5 truncate font-semibold text-ink">{t.normalized_merchant}{t.notes && <StickyNote className="h-3.5 w-3.5 text-warn-500" aria-label="Has note" />}</p>
                            <p className="truncate text-xs text-ink-muted" title={t.raw_description}>{t.raw_description}</p>
                          </div>
                        </div>
                      </td>
                      <td className="table-td"><div className="flex items-center gap-1.5"><CategoryPill name={t.category_name} color={t.category_color} />{t.needs_review && <Badge tone="warn">Review</Badge>}</div></td>
                      <td className="table-td whitespace-nowrap text-ink-soft">{t.payment_method}</td>
                      <td className="table-td hidden max-w-[11rem] truncate text-xs text-ink-muted xl:table-cell">{t.upi_id || '—'}</td>
                      <td className="table-td hidden whitespace-nowrap text-xs text-ink-muted 2xl:table-cell">{t.bank_name}</td>
                      <td className={`table-td whitespace-nowrap text-right font-bold ${t.transaction_type === 'credit' ? 'text-brand-600' : 'text-ink'}`}>{t.transaction_type === 'credit' ? '+' : ''}{formatINR(t.amount, { decimals: true })}</td>
                      <td className="table-td"><TypeBadge type={t.transaction_type} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* mobile list */}
            <ul className="divide-y divide-line md:hidden">
              {data.items.map((t) => (
                <li key={t.id}>
                  <button className="flex w-full items-center gap-3 px-4 py-3 text-left" onClick={() => setSelected(t)}>
                    <MerchantAvatar name={t.normalized_merchant} color={t.category_color} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-ink">{t.normalized_merchant}</p>
                      <p className="truncate text-xs text-ink-muted">{formatDate(t.transaction_date)} · {t.category_name} · {t.payment_method}</p>
                    </div>
                    <p className={`text-sm font-bold ${t.transaction_type === 'credit' ? 'text-brand-600' : 'text-ink'}`}>{t.transaction_type === 'credit' ? '+' : '−'}{formatINR(t.amount)}</p>
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap items-center justify-between">
              <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onPage={(p) => update({ page: p }, false)} />
              <label className="flex items-center gap-2 px-4 pb-3 text-xs text-ink-muted sm:pb-0">Rows
                <select className="select w-auto py-1 text-xs" value={pageSize} onChange={(e) => update({ page_size: e.target.value })}>
                  {[25, 50, 100].map((n) => <option key={n}>{n}</option>)}
                </select>
              </label>
            </div>
          </>
        )}
      </Card>
      <TransactionDetail txn={selected} categories={categories} onClose={() => setSelected(null)} onSaved={() => dataChanged()} />
    </div>
  )
}
