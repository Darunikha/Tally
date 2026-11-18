import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowDownLeft, ArrowUpRight, CreditCard, Landmark, Loader2, Pencil, Plus, Sparkles, Trash2, Wallet } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import AccountForm, { TYPE_LABEL } from '../components/AccountForm'
import { Badge, Card, ConfirmDialog, EmptyState, ErrorState, LoadingBlock, PageHeader, StatCard } from '../components/ui'
import { useFilters } from '../context/FilterContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { formatDate, formatINR } from '../lib/format'

function AccountCard({ a, onEdit, onDelete, onAnalyse }) {
  const card = a.account_type === 'credit_card'
  const month = a.latest_month
  return (
    <Card className="card-pad flex flex-col">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-base font-bold text-ink">
            <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: a.color }} aria-hidden="true" />
            <span className="truncate">{a.name}</span>
            {a.last4 && <span className="shrink-0 text-sm font-medium text-ink-muted" aria-label={`ending ${a.last4}`}>••{a.last4}</span>}
          </h3>
          <p className="mt-1"><Badge tone={card ? 'navy' : 'brand'}>{TYPE_LABEL[a.account_type]}</Badge></p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button className="rounded-lg p-1.5 text-ink-muted hover:bg-canvas hover:text-ink" onClick={() => onEdit(a)} aria-label={`Edit ${a.name}`}><Pencil className="h-4 w-4" /></button>
          <button className="rounded-lg p-1.5 text-ink-muted hover:bg-danger-50 hover:text-danger-600" onClick={() => onDelete(a)} aria-label={`Delete ${a.name}`}><Trash2 className="h-4 w-4" /></button>
        </div>
      </div>

      {a.transaction_count === 0 ? (
        <p className="mt-5 rounded-xl bg-canvas px-4 py-3 text-sm text-ink-muted">No statements yet. File one here when you upload it.</p>
      ) : (
        <>
          <div className="mt-5">
            {card ? (
              <>
                <p className="text-2xl font-extrabold tracking-tight text-ink">{formatINR(month.money_out)}</p>
                <p className="text-xs text-ink-muted">spent in {month.label}</p>
              </>
            ) : a.balance ? (
              <>
                <p className="text-2xl font-extrabold tracking-tight text-ink">{formatINR(a.balance.amount, { decimals: true })}</p>
                <p className="text-xs text-ink-muted">balance as of {formatDate(a.balance.as_of)}</p>
              </>
            ) : <p className="text-sm text-ink-muted">Statements for this account don't include a balance.</p>}
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-xl bg-brand-50/60 px-3 py-2">
              <dt className="flex items-center gap-1 text-xs text-ink-muted"><ArrowDownLeft className="h-3.5 w-3.5 text-brand-600" />{card ? 'Payments & refunds' : 'Money in'}</dt>
              <dd className="font-bold text-ink">{formatINR(month.money_in)}</dd>
            </div>
            {!card && (
              <div className="rounded-xl bg-danger-50/60 px-3 py-2">
                <dt className="flex items-center gap-1 text-xs text-ink-muted"><ArrowUpRight className="h-3.5 w-3.5 text-danger-500" />Money out</dt>
                <dd className="font-bold text-ink">{formatINR(month.money_out)}</dd>
              </div>
            )}
          </dl>
          <p className="mt-3 text-xs text-ink-muted">
            {month.label} · {a.statement_count} statement{a.statement_count === 1 ? '' : 's'} · {a.transaction_count.toLocaleString('en-IN')} transactions
            <br />{formatDate(a.date_range.start)} – {formatDate(a.date_range.end)}
          </p>
        </>
      )}

      <div className="mt-auto flex flex-wrap gap-2 pt-4">
        <button className="btn-secondary btn-sm" onClick={() => onAnalyse(a)} disabled={a.transaction_count === 0}>Analyse</button>
        <Link to={`/transactions?account_id=${a.id}`} className="btn-ghost btn-sm" aria-label={`Transactions in ${a.name}`}>Transactions</Link>
      </div>
    </Card>
  )
}

export default function Accounts() {
  const toast = useToast()
  const navigate = useNavigate()
  const { version, dataChanged, setFilter } = useFilters()
  const { data, loading, error, reload } = useApi('/accounts', undefined, [version])
  const [form, setForm] = useState(null)
  const [removing, setRemoving] = useState(null)
  const [busy, setBusy] = useState(false)

  const refresh = () => { reload(); dataChanged() }
  const remove = async () => {
    setBusy(true)
    try {
      await api.delete(`/accounts/${removing.id}`)
      toast.success('Account deleted. Its statements are kept.')
      setRemoving(null); refresh()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }
  const autoSetup = async () => {
    setBusy(true)
    try {
      const r = (await api.post('/accounts/auto-setup')).data
      toast.success(`${r.assigned_statements} statement${r.assigned_statements === 1 ? '' : 's'} filed, ${r.created_accounts} account${r.created_accounts === 1 ? '' : 's'} created`)
      refresh()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }
  const analyse = (a) => { setFilter((f) => ({ ...f, accountId: a.id, uploadId: '', mode: 'all' })); navigate('/') }

  const t = data?.totals
  const empty = data && data.accounts.length === 0 && !data.unassigned

  return (
    <div className="animate-fade-up">
      <PageHeader title="Accounts" subtitle="Your bank accounts and credit cards, each with its own balance and activity."
        actions={<button className="btn-primary" onClick={() => setForm({})}><Plus className="h-4 w-4" />Add account</button>} />

      {error ? <Card className="card-pad"><ErrorState message={error} onRetry={reload} /></Card> : loading && !data ? (
        <Card className="card-pad"><LoadingBlock rows={5} /></Card>
      ) : empty ? (
        <Card className="card-pad">
          <EmptyState icon={Landmark} title="No accounts yet"
            message="Add the accounts you hold, then choose one when you import a statement. Tally will show each account's balance and let you look at one account or all of them together."
            action={<div className="flex flex-wrap justify-center gap-2">
              <button className="btn-primary" onClick={() => setForm({})}><Plus className="h-4 w-4" />Add an account</button>
              <Link to="/upload" className="btn-secondary">Upload a statement</Link>
            </div>} />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard icon={Wallet} label="In bank accounts" value={t.bank_accounts_with_balance ? formatINR(t.bank_balance) : '—'}
              hint="The latest balance on each bank account's newest statement, added together. Each account's date is shown on its card." />
            <StatCard icon={Landmark} tone="navy" label="Bank accounts" value={`${t.bank_account_count}`} />
            <StatCard icon={CreditCard} tone="warn" label="Credit cards" value={`${t.card_count}`} />
          </div>

          {data.unassigned && (
            <Card className="card-pad mt-6 border-brand-200 bg-brand-50/40">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="max-w-2xl text-sm text-ink-soft">
                  <b className="text-ink">{data.unassigned.statement_count} statement{data.unassigned.statement_count === 1 ? '' : 's'}</b>{' '}
                  ({data.unassigned.transaction_count.toLocaleString('en-IN')} transactions) aren't filed under an account yet.
                  Tally can create one account per bank and file them for you, or you can move them yourself from Statement History.
                </p>
                <button className="btn-primary" onClick={autoSetup} disabled={busy}>
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}Set up automatically
                </button>
              </div>
            </Card>
          )}

          {data.accounts.length > 0 && (
            <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
              {data.accounts.map((a) => <AccountCard key={a.id} a={a} onEdit={(x) => setForm({ initial: x })} onDelete={setRemoving} onAnalyse={analyse} />)}
            </div>
          )}
        </>
      )}

      {form && <AccountForm initial={form.initial} onClose={() => setForm(null)} onSaved={refresh} />}
      <ConfirmDialog open={!!removing} title="Delete this account?" danger confirmLabel="Delete account" busy={busy} onConfirm={remove} onClose={() => setRemoving(null)}
        message={removing ? `${removing.name} will be removed. Its ${removing.statement_count} statement${removing.statement_count === 1 ? '' : 's'} and ${removing.transaction_count.toLocaleString('en-IN')} transactions are kept and become unassigned.` : ''} />
    </div>
  )
}
