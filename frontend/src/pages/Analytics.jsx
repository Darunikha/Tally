import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BarChart3, CalendarDays, CalendarRange, Layers, LineChart as LineIcon, PieChart as PieIcon, Scale, Sparkles, Store, Wallet } from 'lucide-react'
import { CategoryDonut, DualLine, IncomeExpenseBars, RankBars, SimpleBars, TrendArea } from '../components/charts'
import DownloadReportButton from '../components/DownloadReportButton'
import PeriodPicker, { periodLabel } from '../components/layout/PeriodPicker'
import { Card, CardHeader, Delta, EmptyState, ErrorState, LoadingBlock, PageHeader, Segmented } from '../components/ui'
import { useFilters } from '../context/FilterContext'
import { useApi } from '../hooks/useApi'
import { formatINR, pct } from '../lib/format'

function Kpi({ label, value, prev, change, goodWhenUp }) {
  return (
    <div className="rounded-xl bg-canvas p-4">
      <p className="text-xs font-medium text-ink-muted">{label}</p>
      <p className="mt-1 text-xl font-extrabold text-ink">{value}</p>
      <div className="mt-1 flex flex-wrap items-center gap-2">{change !== undefined && <Delta value={change} goodWhenUp={goodWhenUp} suffix="" />}{prev != null && <span className="text-xs text-ink-faint">prev. {prev}</span>}</div>
    </div>
  )
}

const chg = (a, b) => (b ? Math.round(((a - b) / Math.abs(b)) * 1000) / 10 : null)

export default function Analytics() {
  const { params, filter, ready, version } = useFilters()
  const [gran, setGran] = useState('auto')
  const { data, loading, error, reload } = useApi(ready ? '/analytics/overview' : null, { ...params, granularity: gran }, [version])
  const insights = useApi(ready ? '/analytics/insights' : null, params, [version])
  const t = data?.totals
  const p = data?.previous_totals
  const empty = data && t.transaction_count === 0

  return (
    <div className="animate-fade-up">
      <PageHeader title="Analytics" subtitle={`Detailed spending analysis · ${periodLabel(filter)}`} actions={<><DownloadReportButton params={params} /><PeriodPicker /></>} />
      {error ? <Card className="card-pad"><ErrorState message={error} onRetry={reload} /></Card> : empty ? (
        <Card className="card-pad"><EmptyState icon={BarChart3} title="Nothing to analyse for this period" message="Choose a different period or upload a statement." action={<Link to="/upload" className="btn-primary">Upload statement</Link>} /></Card>
      ) : (
        <>
          <Card className="card-pad">
            <CardHeader icon={Scale} title="Period comparison" subtitle={data?.previous_period ? `Compared with ${data.previous_period.start} → ${data.previous_period.end}` : 'No previous period to compare'} />
            {!data ? <LoadingBlock rows={3} /> : (
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Kpi label="Income" value={formatINR(t.total_income)} prev={p && formatINR(p.total_income)} change={p && chg(t.total_income, p.total_income)} goodWhenUp />
                <Kpi label="Expenses" value={formatINR(t.total_expenses)} prev={p && formatINR(p.total_expenses)} change={p && chg(t.total_expenses, p.total_expenses)} goodWhenUp={false} />
                <Kpi label="Avg. daily spend" value={formatINR(t.avg_daily_spending)} prev={p && formatINR(p.avg_daily_spending)} change={p && chg(t.avg_daily_spending, p.avg_daily_spending)} goodWhenUp={false} />
                <Kpi label="Savings rate" value={t.savings_rate == null ? '—' : `${t.savings_rate}%`} prev={p?.savings_rate != null ? `${p.savings_rate}%` : null} change={undefined} />
              </div>
            )}
          </Card>

          <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
            <Card className="card-pad">
              <CardHeader icon={LineIcon} title="Income vs expenses over time"
                action={<Segmented size="sm" value={gran} onChange={setGran} options={[{ value: 'auto', label: 'Auto' }, { value: 'day', label: 'Daily' }, { value: 'week', label: 'Weekly' }, { value: 'month', label: 'Monthly' }]} />} />
              {!data || loading ? <LoadingBlock rows={6} /> : <DualLine data={data.trend} height={280} />}
            </Card>
            <Card className="card-pad">
              <CardHeader icon={PieIcon} title="Spending by category" />
              {!data ? <LoadingBlock rows={6} /> : data.categories.length ? <CategoryDonut rows={data.categories} total={t.total_expenses} max={6} height={200} /> : <EmptyState compact title="No expenses" />}
            </Card>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Card className="card-pad">
              <CardHeader icon={CalendarDays} title="Daily spending" />
              {!data ? <LoadingBlock rows={6} /> : data.daily.length ? <TrendArea data={data.daily} name="Spent" /> : <EmptyState compact title="Range too long for a daily view" message="Pick a shorter period." />}
            </Card>
            <Card className="card-pad">
              <CardHeader icon={CalendarRange} title="Weekly spending" subtitle="Weeks start on Monday" />
              {!data ? <LoadingBlock rows={6} /> : <SimpleBars data={data.weekly.map((w) => ({ label: w.label, amount: w.expense }))} name="Spent" />}
            </Card>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Card className="card-pad">
              <CardHeader icon={BarChart3} title="Monthly income vs expenses" />
              {!data ? <LoadingBlock rows={6} /> : <IncomeExpenseBars data={data.monthly} />}
            </Card>
            <Card className="card-pad">
              <CardHeader icon={CalendarDays} title="Spending by day of week" />
              {!data ? <LoadingBlock rows={6} /> : <SimpleBars data={data.weekday.map((d) => ({ label: d.day, amount: d.amount }))} name="Spent" color="#2F7D55" />}
            </Card>
          </div>

          <Card className="mt-6 overflow-hidden">
            <div className="p-5 pb-0"><CardHeader icon={Layers} title="Category breakdown" subtitle="With change against the previous period" /></div>
            {!data ? <div className="p-5"><LoadingBlock rows={6} /></div> : (
              <div className="scrollbar-thin overflow-x-auto">
                <table className="w-full min-w-[640px]">
                  <thead className="bg-canvas/70"><tr>
                    <th className="table-th">Category</th><th className="table-th text-right">Transactions</th><th className="table-th text-right">Amount</th>
                    <th className="table-th">Share</th><th className="table-th text-right">Previous</th><th className="table-th text-right">Change</th>
                  </tr></thead>
                  <tbody className="divide-y divide-line">
                    {data.categories.map((c) => (
                      <tr key={c.name} className="hover:bg-canvas/60">
                        <td className="table-td"><Link to={c.category_id ? `/transactions?category_id=${c.category_id}` : '/transactions'} className="flex items-center gap-2 font-semibold text-ink hover:text-brand-600"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c.color }} />{c.name}</Link></td>
                        <td className="table-td text-right text-ink-soft">{c.count}</td>
                        <td className="table-td text-right font-bold">{formatINR(c.amount)}</td>
                        <td className="table-td w-48"><div className="flex items-center gap-2"><div className="h-1.5 flex-1 overflow-hidden rounded-full bg-canvas"><div className="h-full rounded-full" style={{ width: `${c.percentage}%`, background: c.color }} /></div><span className="w-10 text-right text-xs text-ink-soft">{c.percentage.toFixed(0)}%</span></div></td>
                        <td className="table-td text-right text-ink-muted">{c.previous_amount ? formatINR(c.previous_amount) : '—'}</td>
                        <td className={`table-td text-right text-xs font-semibold ${c.change == null ? 'text-ink-faint' : c.change > 0 ? 'text-danger-500' : 'text-brand-600'}`}>{c.change == null ? 'new' : pct(c.change)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
            <Card className="card-pad xl:col-span-1">
              <CardHeader icon={Store} title="Top merchants" />
              {!data ? <LoadingBlock rows={6} /> : <RankBars rows={data.merchants.slice(0, 8)} sub={(r) => `${r.count} txns · avg ${formatINR(r.average)}`} />}
            </Card>
            <Card className="card-pad">
              <CardHeader icon={BarChart3} title="Transaction size distribution" subtitle="Number of debits by amount" />
              {!data ? <LoadingBlock rows={6} /> : <SimpleBars data={data.distribution.map((d) => ({ label: d.range, amount: d.count }))} name="Debits" color="#3D5A80" valueFormatter={(v) => v} />}
            </Card>
            <Card className="card-pad">
              <CardHeader icon={Wallet} title="Payment methods" />
              {!data ? <LoadingBlock rows={6} /> : <RankBars rows={data.payment_methods} labelKey="method" valueKey="amount" color="#3D5A80" sub={(r) => `${r.count} debits`} />}
            </Card>
          </div>

          <Card className="card-pad mt-6">
            <CardHeader icon={Sparkles} title="Insights" subtitle="Computed only from your transactions" />
            {insights.loading && !insights.data ? <LoadingBlock rows={4} /> : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {(insights.data || []).map((i) => (
                  <div key={i.id} className={`rounded-xl border p-4 ${i.tone === 'negative' ? 'border-danger-100 bg-danger-50/50' : i.tone === 'positive' ? 'border-brand-100 bg-brand-50/50' : 'border-line bg-canvas/60'}`}>
                    <p className="text-sm font-bold text-ink">{i.title}</p>
                    <p className="mt-1 text-sm text-ink-soft">{i.message}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
