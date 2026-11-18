import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight, BarChart3, CalendarClock, CloudUpload, Hash, History, Lightbulb, PieChart as PieIcon, Receipt,
  Scale, Store, Wallet, Zap,
} from 'lucide-react'
import BudgetsCard from '../components/BudgetProgress'
import CardPaymentsNote from '../components/CardPaymentsNote'
import DownloadReportButton from '../components/DownloadReportButton'
import { CategoryDonut, IncomeExpenseBars, RankBars, TrendArea } from '../components/charts'
import PeriodPicker, { periodLabel } from '../components/layout/PeriodPicker'
import TransactionDetail, { MerchantAvatar, useCategories } from '../components/TransactionDetail'
import { Card, CardHeader, EmptyState, ErrorState, LoadingBlock, Segmented, StatCard, TypeBadge } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useFilters } from '../context/FilterContext'
import { useApi } from '../hooks/useApi'
import { firstName, formatDate, formatINR, greeting } from '../lib/format'
import { add, toISO } from '../lib/dates'

function KeyInsight({ insights }) {
  const [i, setI] = useState(0)
  if (!insights?.length) return null
  const cur = insights[i % insights.length]
  return (
    <Card className="card-pad relative flex flex-col overflow-hidden bg-gradient-to-br from-brand-50 via-white to-brand-50/40">
      <div className="mb-3 flex items-center gap-2.5">
        <Lightbulb className="h-5 w-5 text-warn-500" />
        <h2 className="text-base font-bold text-ink sm:text-lg">Key insight</h2>
        <span className="ml-auto text-xs text-ink-muted">{(i % insights.length) + 1} / {insights.length}</span>
      </div>
      <p className="max-w-md text-lg font-semibold leading-snug text-ink sm:text-xl">{cur.message}</p>
      <ul className="mt-5 space-y-2.5 border-t border-brand-100 pt-4">
        {[1, 2, 3].map((k) => insights[(i + k) % insights.length]).filter((x, k, arr) => insights.length > k + 1 && arr.indexOf(x) === k).map((x) => (
          <li key={x.id} className="flex gap-2.5 text-sm text-ink-soft">
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${x.tone === 'negative' ? 'bg-danger-500' : x.tone === 'positive' ? 'bg-brand-500' : 'bg-ink-faint'}`} />
            <span><b className="font-semibold text-ink">{x.title}.</b> {x.message}</span>
          </li>
        ))}
      </ul>
      <div className="mt-auto flex items-center gap-2 pt-5">
        {insights.map((x, k) => (
          <button key={x.id} onClick={() => setI(k)} aria-label={`Insight ${k + 1}`}
            className={`h-1.5 rounded-full transition-all ${k === i % insights.length ? 'w-6 bg-brand-500' : 'w-1.5 bg-brand-200 hover:bg-brand-300'}`} />
        ))}
        <button className="btn-ghost btn-sm ml-auto" onClick={() => setI((v) => v + 1)}>Next<ArrowRight className="h-3.5 w-3.5" /></button>
      </div>
      <svg viewBox="0 0 120 120" className="pointer-events-none absolute -bottom-6 -right-6 h-32 w-32 opacity-[0.08]" aria-hidden="true"><path d="M10 110C10 50 50 12 110 10c0 60-38 100-98 100H10Z" fill="#2F7D55" /></svg>
    </Card>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const { params, filter, ready, version, dataChanged, periods } = useFilters()
  const [range, setRange] = useState('1M')
  const [selected, setSelected] = useState(null)
  const navigate = useNavigate()
  const categories = useCategories([version])
  const { data, loading, error, reload } = useApi(ready ? '/analytics/dashboard' : null, params, [version])

  // 3M / 6M trend: weekly series ending at the selected period's end
  const trendParams = useMemo(() => {
    if (range === '1M' || !data?.period) return null
    const end = data.period.end
    const start = toISO(add(new Date(`${end.slice(0, 7)}-01T00:00:00`), { months: range === '3M' ? -2 : -5 }))
    return { start, end, granularity: 'week', upload_id: params.upload_id }
  }, [range, data, params.upload_id])
  const longTrend = useApi(trendParams ? '/analytics/overview' : null, trendParams, [version])
  const trendData = range === '1M' ? data?.daily_trend : longTrend.data?.trend

  // budgets are monthly: follow the picked month, otherwise the latest month with data
  const budgetMonth = filter.mode === 'month' && filter.month ? { month: filter.month, year: filter.year }
    : periods.latest ? { month: periods.latest.month, year: periods.latest.year } : undefined
  const budgets = useApi(ready ? '/budgets/status' : null, budgetMonth, [version])

  const t = data?.totals
  const empty = data && t.transaction_count === 0
  const label = periodLabel(filter)

  return (
    <div className="animate-fade-up">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-ink sm:text-[2.6rem] sm:leading-tight">{greeting()}, {firstName(user?.full_name)}! <span aria-hidden="true">🌱</span></h1>
          <p className="mt-1 text-base text-ink-muted sm:text-lg">Here's your spending summary for {label}</p>
        </div>
        <div className="flex items-center gap-2"><DownloadReportButton params={params} /><PeriodPicker /></div>
      </div>

      {error ? <Card className="card-pad"><ErrorState message={error} onRetry={reload} /></Card> : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <StatCard icon={Wallet} label="Total Income" value={formatINR(t?.total_income)} delta={data?.changes.total_income} goodWhenUp loading={loading && !data} />
            <StatCard icon={Receipt} tone="danger" label="Total Expenses" value={formatINR(t?.total_expenses)} delta={data?.changes.total_expenses} goodWhenUp={false} loading={loading && !data} />
            <StatCard icon={Scale} label="Net Balance" value={formatINR(t?.net_balance)} delta={data?.changes.net_balance} goodWhenUp loading={loading && !data}
              hint="Income minus expenses for the selected period." />
            <StatCard icon={Hash} tone="navy" label="Transactions" value={t?.transaction_count?.toLocaleString('en-IN') ?? '—'} delta={data?.changes.transaction_count} goodWhenUp={false} loading={loading && !data} />
            <StatCard icon={Zap} tone="navy" label="UPI Spending" value={formatINR(t?.upi_spending)} delta={data?.changes.upi_spending} goodWhenUp={false} loading={loading && !data}
              hint={t ? `${t.upi_transaction_count} UPI debits` : undefined} />
            <StatCard icon={CalendarClock} tone="warn" label="Avg. Daily Spending" value={formatINR(t?.avg_daily_spending)} delta={data?.changes.avg_daily_spending} goodWhenUp={false} loading={loading && !data}
              hint={t ? `Total expenses ÷ ${t.days} days in the period.` : undefined} />
          </div>

          <CardPaymentsNote count={data?.excluded_payments?.count} />

          {empty && !loading ? (
            <Card className="card-pad mt-6">
              <EmptyState icon={CloudUpload} title={`No transactions for ${label}`}
                message="Upload a bank statement to see your spending, or pick another period with the date selector above."
                action={<div className="flex flex-wrap justify-center gap-2"><Link to="/upload" className="btn-primary"><CloudUpload className="h-4 w-4" />Upload statement</Link><Link to="/settings" className="btn-secondary">Try demo data</Link></div>} />
            </Card>
          ) : (
            <>
              <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
                <Card className="card-pad">
                  <CardHeader icon={BarChart3} title="Spending Trend" subtitle={range === '1M' ? `Daily spend · ${label}` : `Weekly spend · last ${range === '3M' ? 3 : 6} months`}
                    action={<Segmented size="sm" value={range} onChange={setRange} options={[{ value: '1M', label: '1M' }, { value: '3M', label: '3M' }, { value: '6M', label: '6M' }]} />} />
                  {(loading && !data) || (range !== '1M' && longTrend.loading) ? <LoadingBlock rows={6} /> : <TrendArea data={trendData || []} name="Spent" />}
                </Card>
                <Card className="card-pad">
                  <CardHeader icon={PieIcon} title="Expenses by Category" subtitle="Click a slice to see its transactions" />
                  {loading && !data ? <LoadingBlock rows={6} /> : data.category_breakdown.length ? (
                    <CategoryDonut rows={data.category_breakdown} total={t.total_expenses}
                      onSelect={(d) => d.category_id && navigate(`/transactions?category_id=${d.category_id}`)} />
                  ) : <EmptyState compact title="No expenses" message="No debit transactions in this period." />}
                </Card>
              </div>

              <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
                <Card className="card-pad">
                  <CardHeader icon={History} title="Recent Transactions" action={<Link to="/transactions" className="inline-flex items-center gap-1 text-sm font-semibold text-brand-600 hover:underline">View all<ArrowRight className="h-4 w-4" /></Link>} />
                  {loading && !data ? <LoadingBlock rows={5} /> : (
                    <ul className="divide-y divide-line">
                      {data.recent_transactions.map((r) => (
                        <li key={r.id}>
                          <button onClick={() => setSelected(r)} className="flex w-full items-center gap-3 py-3 text-left transition hover:bg-canvas/60 sm:gap-4">
                            <MerchantAvatar name={r.normalized_merchant} color={r.category_color} />
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-sm font-semibold text-ink">{r.normalized_merchant}</p>
                              <p className="truncate text-xs text-ink-muted">{r.category_name || 'Uncategorised'} · {r.payment_method}</p>
                            </div>
                            <div className="text-right">
                              <p className={`text-sm font-bold ${r.transaction_type === 'credit' ? 'text-brand-600' : 'text-ink'}`}>{r.transaction_type === 'credit' ? '+' : ''}{formatINR(r.amount)}</p>
                              <p className="text-xs text-ink-muted">{formatDate(r.transaction_date)}</p>
                            </div>
                            <span className="hidden w-16 justify-end sm:flex"><TypeBadge type={r.transaction_type} /></span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
                <KeyInsight insights={data?.insights} />
              </div>

              <BudgetsCard data={budgets.data} loading={budgets.loading} error={budgets.error} />

              <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
                <Card className="card-pad">
                  <CardHeader icon={BarChart3} title="Monthly Income vs Expenses" subtitle="Last 6 months" />
                  {loading && !data ? <LoadingBlock rows={6} /> : <IncomeExpenseBars data={data.monthly} />}
                </Card>
                <Card className="card-pad">
                  <CardHeader icon={Store} title="Top Spending Merchants" action={<Link to="/upi" className="text-sm font-semibold text-brand-600 hover:underline">UPI details</Link>} />
                  {loading && !data ? <LoadingBlock rows={6} /> : data.top_merchants.length ? (
                    <RankBars rows={data.top_merchants} sub={(r) => `${r.count} payment${r.count > 1 ? 's' : ''} · avg ${formatINR(r.average)}${r.category ? ' · ' + r.category : ''}`} />
                  ) : <EmptyState compact title="No merchants yet" />}
                </Card>
              </div>
            </>
          )}
        </>
      )}
      <TransactionDetail txn={selected} categories={categories} onClose={() => setSelected(null)} onSaved={() => dataChanged()} />
    </div>
  )
}
