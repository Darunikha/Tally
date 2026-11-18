import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, CalendarClock, CalendarDays, CloudUpload, Repeat, RotateCcw, TrendingUp, Wallet } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import { MerchantAvatar } from '../components/TransactionDetail'
import { Badge, Card, CardHeader, CategoryPill, EmptyState, ErrorState, LoadingBlock, PageHeader, Segmented, StatCard } from '../components/ui'
import { useFilters } from '../context/FilterContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { formatDate, formatINR } from '../lib/format'

export const CADENCE_LABEL = { weekly: 'Weekly', monthly: 'Monthly', quarterly: 'Every 3 months', yearly: 'Yearly' }
const TABS = [
  { value: 'all', label: 'All' }, { value: 'subscription', label: 'Subscriptions' },
  { value: 'bill', label: 'Bills & rent' }, { value: 'other', label: 'Other' },
]

export const amountText = (item) => `${item.amount_kind === 'variable' ? '~' : ''}${formatINR(item.amount)}`

export function dueText(days) {
  if (days === 0) return 'today'
  const n = Math.abs(days)
  const unit = `${n} day${n === 1 ? '' : 's'}`
  return days > 0 ? `in ${unit}` : `${unit} ago`
}

function PriceChange({ change }) {
  const up = change.percent > 0
  return (
    <Badge tone={up ? 'danger' : 'brand'}>
      {up ? 'Price up' : 'Price down'} {Math.abs(change.percent)}% ({formatINR(change.from)} → {formatINR(change.to)})
    </Badge>
  )
}

function Row({ item, onToggle, busy }) {
  const lapsed = item.status === 'lapsed'
  return (
    <li className={`flex flex-wrap items-center gap-x-4 gap-y-3 py-4 ${item.ignored ? 'opacity-60' : ''}`}>
      <MerchantAvatar name={item.merchant} color={item.category_color} />
      <div className="min-w-0 flex-1 basis-48">
        <p className="flex flex-wrap items-center gap-2">
          <span className="truncate font-semibold text-ink">{item.merchant}</span>
          <Badge tone="navy">{CADENCE_LABEL[item.cadence]}</Badge>
          {lapsed && <Badge tone="warn">Not seen lately</Badge>}
          {item.price_change && <PriceChange change={item.price_change} />}
        </p>
        <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
          <CategoryPill name={item.category} color={item.category_color} />
          <span>{item.occurrences} payments since {formatDate(item.first_date)}</span>
          <span>Last paid {formatDate(item.last_date)}</span>
        </p>
      </div>
      <div className="text-right">
        <p className="text-base font-bold text-ink" title={item.amount_kind === 'variable' ? 'The amount varies each time; this is the typical amount' : undefined}>
          {amountText(item)}
        </p>
        <p className="text-xs text-ink-muted">
          {lapsed ? `${formatINR(item.monthly_cost)} / month when active` : <>Next {formatDate(item.next_expected, { year: false })} · {dueText(item.due_in_days)}</>}
        </p>
      </div>
      <button className="btn-ghost btn-sm" disabled={busy} onClick={() => onToggle(item)}
        aria-label={item.ignored ? `Restore ${item.merchant}` : `${item.merchant} is not recurring`}>
        {item.ignored ? <><RotateCcw className="h-3.5 w-3.5" />Restore</> : 'Not recurring'}
      </button>
    </li>
  )
}

export default function Recurring() {
  const toast = useToast()
  const { version, dataChanged } = useFilters()
  const { data, loading, error, reload } = useApi('/recurring', undefined, [version])
  const [tab, setTab] = useState('all')
  const [showStopped, setShowStopped] = useState(false)
  const [showIgnored, setShowIgnored] = useState(false)
  const [busy, setBusy] = useState(false)

  const toggle = async (item) => {
    setBusy(true)
    try {
      await api.put('/recurring/ignored', { merchant: item.merchant, ignored: !item.ignored })
      toast.success(item.ignored ? `${item.merchant} is back in your list` : `${item.merchant} hidden. You can restore it any time.`)
      reload(); dataChanged()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }

  const items = data?.items || []
  // restoring the last hidden payment must not leave you on an empty "Hidden" view with no way back
  const hiddenView = showIgnored && (data?.ignored_count || 0) > 0
  const visible = items.filter((i) => (hiddenView ? i.ignored : !i.ignored) && (hiddenView || showStopped || i.status === 'active')
    && (tab === 'all' || i.group === tab))
  const s = data?.summary

  return (
    <div className="animate-fade-up">
      <PageHeader title="Recurring payments" subtitle="Subscriptions, bills, rent and SIPs that Tally found in your statements." />

      {error ? <Card className="card-pad"><ErrorState message={error} onRetry={reload} /></Card> : loading && !data ? (
        <Card className="card-pad"><LoadingBlock rows={6} /></Card>
      ) : items.length === 0 ? (
        <Card className="card-pad">
          <EmptyState icon={Repeat} title="No recurring payments found yet"
            message="Tally looks for payments to the same place on a steady schedule, such as three months of the same subscription. Import a few months of statements and they'll show up here."
            action={<Link to="/upload" className="btn-primary"><CloudUpload className="h-4 w-4" />Upload a statement</Link>} />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard icon={Wallet} label="Monthly commitments" value={formatINR(s.monthly_total)}
              hint="Everything active, with quarterly and yearly payments spread across the months." />
            <StatCard icon={CalendarDays} tone="navy" label="Per year" value={formatINR(s.yearly_total)} />
            <StatCard icon={Repeat} tone="warn" label="Active" value={`${s.active_count}`}
              hint={s.lapsed_count ? `${s.lapsed_count} more haven't been seen lately.` : undefined} />
          </div>
          <p className="mt-3 text-xs text-ink-muted">Based on your statements up to {formatDate(data.as_of)}. Amounts marked ~ vary each time.</p>

          {s.upcoming.length > 0 && (
            <Card className="card-pad mt-6">
              <CardHeader icon={CalendarClock} title="Coming up" subtitle="Expected in the 30 days after your latest transaction"
                action={<span className="text-sm font-bold text-ink">{formatINR(s.upcoming_total)}</span>} />
              <ul className="divide-y divide-line" aria-label="Upcoming payments">
                {s.upcoming.map((u) => (
                  <li key={u.merchant} className="flex items-center gap-3 py-2.5">
                    <MerchantAvatar name={u.merchant} color={u.category_color} size="sm" />
                    <span className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">{u.merchant}</span>
                    <span className="text-xs text-ink-muted">{formatDate(u.date, { year: false })} · {dueText(u.due_in_days)}</span>
                    <span className="w-24 text-right text-sm font-bold text-ink">{u.amount_kind === 'variable' ? '~' : ''}{formatINR(u.amount)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card className="card-pad mt-6">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
              <Segmented value={tab} onChange={setTab} options={TABS} />
              <div className="flex flex-wrap items-center gap-4 text-sm">
                {s.lapsed_count > 0 && !hiddenView && (
                  <label className="flex cursor-pointer items-center gap-2 text-ink-soft">
                    <input type="checkbox" className="h-4 w-4 rounded border-line accent-brand-500" checked={showStopped} onChange={(e) => setShowStopped(e.target.checked)} />
                    Show not seen lately ({s.lapsed_count})
                  </label>
                )}
                {data.ignored_count > 0 && (
                  <button className="font-semibold text-brand-600 hover:underline" onClick={() => setShowIgnored((v) => !v)}>
                    {hiddenView ? 'Back to recurring' : `Hidden (${data.ignored_count})`}
                  </button>
                )}
              </div>
            </div>
            {visible.length === 0 ? (
              <EmptyState compact icon={TrendingUp} title={hiddenView ? 'Nothing hidden' : 'Nothing here'}
                message={hiddenView ? 'Payments you mark as not recurring will appear here.' : 'No active recurring payments in this group.'} />
            ) : (
              <ul className="divide-y divide-line" aria-label="Recurring payments">
                {visible.map((i) => <Row key={i.merchant} item={i} onToggle={toggle} busy={busy} />)}
              </ul>
            )}
            {!hiddenView && items.some((i) => !i.ignored) && (
              <p className="mt-3 flex items-center gap-1.5 border-t border-line pt-3 text-xs text-ink-muted">
                <ArrowRight className="h-3.5 w-3.5" />Something here isn't really recurring? Choose "Not recurring" and it won't count towards your totals.
              </p>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
