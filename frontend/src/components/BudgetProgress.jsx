import { Link } from 'react-router-dom'
import { ArrowRight, PiggyBank } from 'lucide-react'
import { Badge, Card, CardHeader, LoadingBlock } from './ui'
import { formatINR } from '../lib/format'

export const STATUS = {
  ok: { label: 'On track', tone: 'brand', bar: 'bg-brand-solid' },
  warning: { label: 'Nearly there', tone: 'warn', bar: 'bg-warn-500' },
  over: { label: 'Over budget', tone: 'danger', bar: 'bg-danger-solid' },
}

/** Words, not just colour, say how a budget is going. */
export function remainingText(b) {
  if (b.status === 'over') return `${formatINR(-b.remaining)} over`
  return `${formatINR(b.remaining)} left`
}

export function BudgetBar({ budget }) {
  const pct = Math.min(100, Math.max(0, budget.percent))
  return (
    <div role="progressbar" aria-label={`${budget.name} budget`} aria-valuemin={0} aria-valuemax={100}
      aria-valuenow={Math.round(Math.min(budget.percent, 100))} aria-valuetext={`${budget.percent}% spent, ${STATUS[budget.status].label}`}
      className="h-2.5 w-full overflow-hidden rounded-full bg-line">
      <div className={`h-full rounded-full transition-all ${STATUS[budget.status].bar}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

function CompactRow({ b }) {
  return (
    <li className="min-w-0">
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="flex min-w-0 items-center gap-2 text-sm font-semibold text-ink">
          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: b.color }} aria-hidden="true" />
          <span className="truncate">{b.name}</span>
        </span>
        <span className="shrink-0 text-xs text-ink-muted">
          <b className="font-bold text-ink">{formatINR(b.spent)}</b> / {formatINR(b.monthly_limit)}
        </span>
      </div>
      <BudgetBar budget={b} />
      <p className={`mt-1 text-xs ${b.status === 'over' ? 'font-semibold text-danger-600' : b.status === 'warning' ? 'font-semibold text-warn-500' : 'text-ink-muted'}`}>
        {Math.round(b.percent)}% used · {remainingText(b)}
      </p>
    </li>
  )
}

/** Dashboard summary: the budgets needing the most attention for the shown month. */
export default function BudgetsCard({ data, loading, error }) {
  if (error) return null // the dashboard is useful without this card
  const rows = data ? [...(data.overall ? [data.overall] : []), ...data.budgets] : []
  const shown = [...rows].sort((a, b) => b.percent - a.percent).slice(0, 4)
  const needAttention = data ? data.summary.over + data.summary.warning : 0

  return (
    <Card className="card-pad mt-6">
      <CardHeader icon={PiggyBank} title="Budgets" subtitle={data ? data.month.label : undefined}
        action={<Link to="/budgets" className="inline-flex items-center gap-1 text-sm font-semibold text-brand-600 hover:underline">{rows.length ? 'Manage' : 'Set up'}<ArrowRight className="h-4 w-4" /></Link>} />
      {loading && !data ? <LoadingBlock rows={3} /> : !rows.length ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-canvas px-4 py-3.5">
          <p className="text-sm text-ink-soft">Set a monthly limit for the categories you want to keep an eye on, and Tally will show how you're tracking.</p>
          <Link to="/budgets" className="btn-primary btn-sm shrink-0">Create a budget</Link>
        </div>
      ) : (
        <>
          {needAttention > 0 && (
            <p className="mb-4"><Badge tone={data.summary.over ? 'danger' : 'warn'}>
              {data.summary.over ? `${data.summary.over} over budget` : `${data.summary.warning} nearing the limit`}
            </Badge></p>
          )}
          <ul className="grid grid-cols-1 gap-x-8 gap-y-5 md:grid-cols-2">{shown.map((b) => <CompactRow key={b.id} b={b} />)}</ul>
        </>
      )}
    </Card>
  )
}
