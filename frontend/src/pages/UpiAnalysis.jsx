import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDownLeft, ArrowUpRight, Hash, Percent, Repeat, Search, Store, TrendingUp, Users, Zap } from 'lucide-react'
import { RankBars, SimpleBars, TrendArea } from '../components/charts'
import PeriodPicker, { periodLabel } from '../components/layout/PeriodPicker'
import { MerchantAvatar } from '../components/TransactionDetail'
import { Card, CardHeader, CategoryPill, EmptyState, ErrorState, LoadingBlock, PageHeader, StatCard } from '../components/ui'
import { useFilters } from '../context/FilterContext'
import { useApi } from '../hooks/useApi'
import { formatDate, formatINR } from '../lib/format'

export default function UpiAnalysis() {
  const { params, filter, ready, version } = useFilters()
  const { data, loading, error, reload } = useApi(ready ? '/upi/summary' : null, params, [version])
  const [q, setQ] = useState('')
  const [sortBy, setSortBy] = useState('total')
  const t = data?.totals
  const empty = data && t.upi_debit_count === 0 && t.upi_credit_count === 0

  const merchants = (data?.merchants || [])
    .filter((m) => !q || m.merchant.toLowerCase().includes(q.toLowerCase()) || m.upi_ids.some((u) => u.includes(q.toLowerCase())))
    .sort((a, b) => b[sortBy] - a[sortBy] || b.total - a.total)

  const flow = t ? [
    { label: 'To merchants (P2M)', amount: t.p2m_amount },
    { label: 'To people (P2A)', amount: t.p2a_amount },
    { label: 'Unspecified', amount: t.unknown_flow_amount },
  ] : []

  return (
    <div className="animate-fade-up">
      <PageHeader title="UPI Analysis" subtitle={`UPI merchant intelligence for ${periodLabel(filter)}`} actions={<PeriodPicker />} />
      {error ? <Card className="card-pad"><ErrorState message={error} onRetry={reload} /></Card> : empty ? (
        <Card className="card-pad"><EmptyState icon={Zap} title="No UPI transactions in this period" message="UPI payments are detected automatically from statement narrations (UPI/…, VPA@bank). Try another period." /></Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard icon={ArrowUpRight} tone="danger" label="UPI Spent" value={formatINR(t?.upi_spent)} loading={!data} hint={t ? `${t.upi_debit_count} UPI payments` : undefined} />
            <StatCard icon={ArrowDownLeft} label="UPI Received" value={formatINR(t?.upi_received)} loading={!data} hint={t ? `${t.upi_credit_count} incoming UPI transfers` : undefined} />
            <StatCard icon={Percent} tone="navy" label="Share of Spending" value={t ? `${t.share_of_spending}%` : '—'} loading={!data} hint="UPI debits as a share of all debits in the period." />
            <StatCard icon={Hash} tone="warn" label="Average Ticket" value={formatINR(t?.average_ticket)} loading={!data} hint={t ? `${t.unique_merchants} unique payees` : undefined} />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
            <Card className="card-pad">
              <CardHeader icon={TrendingUp} title="UPI Spending Trend" />
              {!data ? <LoadingBlock rows={6} /> : <TrendArea data={data.trend} name="UPI spent" color="#1BAF7A" />}
            </Card>
            <Card className="card-pad">
              <CardHeader icon={Users} title="Who you pay" subtitle="Merchant vs person-to-person UPI" />
              {!data ? <LoadingBlock rows={4} /> : <SimpleBars data={flow} name="Spent" color="#3D5A80" height={220} />}
            </Card>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card className="card-pad">
              <CardHeader icon={Store} title="Top UPI merchants by amount" />
              {!data ? <LoadingBlock rows={6} /> : <RankBars rows={data.top_by_amount.slice(0, 8)} sub={(r) => `${r.count} payment${r.count === 1 ? '' : 's'} · avg ${formatINR(r.average)}`} />}
            </Card>
            <Card className="card-pad">
              <CardHeader icon={Repeat} title="Most frequently used" />
              {!data ? <LoadingBlock rows={6} /> : (
                <ul className="divide-y divide-line">
                  {data.top_by_frequency.slice(0, 8).map((m, i) => (
                    <li key={m.merchant} className="flex items-center gap-3 py-2.5">
                      <span className="w-5 text-xs font-bold text-ink-faint">{i + 1}</span>
                      <MerchantAvatar name={m.merchant} color={m.category_color} size="sm" />
                      <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-ink">{m.merchant}</p><p className="truncate text-xs text-ink-muted">{m.upi_ids[0] || 'UPI'}</p></div>
                      <div className="text-right"><p className="text-sm font-bold text-ink">{m.count}×</p><p className="text-xs text-ink-muted">{formatINR(m.total)}</p></div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <Card className="mt-6 overflow-hidden">
            <div className="flex flex-wrap items-center gap-3 p-5">
              <h2 className="mr-auto text-lg font-bold text-ink">All UPI payees</h2>
              <label className="relative">
                <span className="sr-only">Search payees</span>
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
                <input className="input w-56 py-2 pl-9" placeholder="Merchant or UPI ID" value={q} onChange={(e) => setQ(e.target.value)} />
              </label>
              <select className="select w-auto py-2" aria-label="Sort by" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                <option value="total">Sort: total spent</option><option value="count">Sort: transactions</option><option value="average">Sort: average</option>
              </select>
            </div>
            {!data ? <div className="p-5"><LoadingBlock rows={6} /></div> : (
              <div className="scrollbar-thin overflow-x-auto">
                <table className="w-full min-w-[720px]">
                  <thead className="bg-canvas/70"><tr>
                    <th className="table-th">Merchant</th><th className="table-th">UPI IDs</th><th className="table-th">Category</th>
                    <th className="table-th text-right">Payments</th><th className="table-th text-right">Total</th><th className="table-th text-right">Average</th><th className="table-th">Last paid</th>
                  </tr></thead>
                  <tbody className="divide-y divide-line">
                    {merchants.map((m) => (
                      <tr key={m.merchant} className="hover:bg-canvas/60">
                        <td className="table-td"><Link to={`/transactions?merchant=${encodeURIComponent(m.merchant)}&payment_method=UPI`} className="flex items-center gap-2.5 font-semibold text-ink hover:text-brand-600"><MerchantAvatar name={m.merchant} color={m.category_color} size="sm" />{m.merchant}</Link></td>
                        <td className="table-td max-w-[14rem] truncate text-xs text-ink-muted" title={m.upi_ids.join(', ')}>{m.upi_ids.join(', ') || '—'}</td>
                        <td className="table-td"><CategoryPill name={m.category} color={m.category_color} /></td>
                        <td className="table-td text-right">{m.count}</td>
                        <td className="table-td text-right font-bold">{formatINR(m.total)}</td>
                        <td className="table-td text-right text-ink-soft">{formatINR(m.average)}</td>
                        <td className="table-td whitespace-nowrap text-ink-soft">{formatDate(m.last_date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {merchants.length === 0 && <EmptyState compact title="No matching payees" />}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
