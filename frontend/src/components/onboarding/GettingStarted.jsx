import { Link } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Circle, Rocket, X } from 'lucide-react'
import { Card, CardHeader } from '../ui'

/** Dashboard checklist. Steps tick themselves from the user's real data; "Hide" dismisses it for good. */
export default function GettingStarted({ onboarding, onHide }) {
  const { steps, completed, total } = onboarding
  const next = steps.find((s) => !s.done)
  return (
    <Card className="card-pad mb-6 border-brand-200 bg-gradient-to-br from-brand-50/70 to-surface">
      <CardHeader icon={Rocket} title="Get set up" subtitle={`${completed} of ${total} done`}
        action={<button className="btn-ghost btn-sm" onClick={onHide} aria-label="Hide the getting started checklist"><X className="h-3.5 w-3.5" />Hide</button>} />
      <div role="progressbar" aria-label="Getting started progress" aria-valuemin={0} aria-valuemax={total} aria-valuenow={completed}
        className="mb-4 h-2 overflow-hidden rounded-full bg-line">
        <div className="h-full rounded-full bg-brand-solid transition-all" style={{ width: `${(completed / total) * 100}%` }} />
      </div>
      <ol className="space-y-1">
        {steps.map((s) => (
          <li key={s.key} className={`flex items-start gap-3 rounded-xl px-2 py-2.5 ${s.key === next?.key ? 'bg-surface/80 ring-1 ring-brand-100' : ''}`}>
            {s.done
              ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" aria-label="Done" />
              : <Circle className="mt-0.5 h-5 w-5 shrink-0 text-ink-faint" aria-label="Not done yet" />}
            <div className="min-w-0 flex-1">
              <p className={`text-sm font-semibold ${s.done ? 'text-ink-muted line-through decoration-ink-faint/60' : 'text-ink'}`}>{s.title}</p>
              {!s.done && <p className="mt-0.5 text-xs text-ink-muted">{s.description}</p>}
            </div>
            {!s.done && (
              <Link to={s.href} className={`${s.key === next?.key ? 'btn-primary' : 'btn-secondary'} btn-sm shrink-0`} aria-label={`${s.title}: go`}>
                Go<ArrowRight className="h-3.5 w-3.5" />
              </Link>
            )}
          </li>
        ))}
      </ol>
    </Card>
  )
}
