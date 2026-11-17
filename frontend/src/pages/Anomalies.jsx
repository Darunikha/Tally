import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, EyeOff, Info, RotateCcw, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import PeriodPicker, { periodLabel } from '../components/layout/PeriodPicker'
import { Badge, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, Segmented, SeverityBadge } from '../components/ui'
import { useFilters } from '../context/FilterContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { formatDate, formatINR } from '../lib/format'

function AnomalyCard({ a, onReview }) {
  const [open, setOpen] = useState(false)
  const accent = a.severity === 'high' ? 'border-l-danger-500' : a.severity === 'medium' ? 'border-l-warn-500' : 'border-l-ink-faint'
  return (
    <Card className={`border-l-4 ${accent} p-5 ${a.status !== 'open' ? 'opacity-70' : ''}`}>
      <div className="flex flex-wrap items-start gap-3">
        <AlertTriangle className={`mt-0.5 h-5 w-5 shrink-0 ${a.severity === 'high' ? 'text-danger-500' : a.severity === 'medium' ? 'text-warn-500' : 'text-ink-muted'}`} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-bold text-ink">{a.type_label}</h3>
            <SeverityBadge severity={a.severity} />
            {a.status !== 'open' && <Badge tone="brand">{a.status === 'reviewed' ? 'Reviewed' : 'Dismissed'}</Badge>}
          </div>
          <p className="mt-1 text-sm text-ink-soft">{a.reason}</p>
          <p className="mt-1 text-xs text-ink-muted">{formatDate(a.date)} · {formatINR(a.amount)} · {a.transactions.length} transaction{a.transactions.length > 1 ? 's' : ''}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {a.status === 'open' ? (<>
            <button className="btn-secondary btn-sm" onClick={() => onReview(a, 'reviewed')}><CheckCircle2 className="h-3.5 w-3.5" />Mark reviewed</button>
            <button className="btn-ghost btn-sm" onClick={() => onReview(a, 'dismissed')}><EyeOff className="h-3.5 w-3.5" />Dismiss</button>
          </>) : <button className="btn-ghost btn-sm" onClick={() => onReview(a, 'open')}><RotateCcw className="h-3.5 w-3.5" />Reopen</button>}
        </div>
      </div>
      <button className="mt-3 text-xs font-semibold text-brand-600 hover:underline" onClick={() => setOpen((o) => !o)}>{open ? 'Hide' : 'Show'} transactions</button>
      {open && (
        <div className="scrollbar-thin mt-3 overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[560px]">
            <thead className="bg-canvas/70"><tr><th className="table-th">Date</th><th className="table-th">Merchant</th><th className="table-th">Method</th><th className="table-th">Category</th><th className="table-th text-right">Amount</th></tr></thead>
            <tbody className="divide-y divide-line">
              {a.transactions.map((t) => (
                <tr key={t.id}>
                  <td className="table-td whitespace-nowrap text-ink-soft">{formatDate(t.date)}</td>
                  <td className="table-td max-w-[16rem]"><p className="truncate font-semibold text-ink">{t.merchant}</p><p className="truncate text-xs text-ink-muted" title={t.description}>{t.description}</p></td>
                  <td className="table-td text-ink-soft">{t.payment_method}{t.upi_id ? <span className="block text-xs text-ink-faint">{t.upi_id}</span> : null}</td>
                  <td className="table-td text-ink-soft">{t.category || '—'}</td>
                  <td className="table-td text-right font-bold">{formatINR(t.amount, { decimals: true })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

export default function Anomalies() {
  const toast = useToast()
  const { params, filter, ready, version, dataChanged } = useFilters()
  const [status, setStatus] = useState('open')
  const [severity, setSeverity] = useState('')
  const { data, loading, error, reload } = useApi(ready ? '/anomalies' : null, { ...params, status: status === 'all' ? '' : status, severity }, [version])

  const review = async (a, s) => {
    try {
      await api.put(`/anomalies/${a.key}/review`, { status: s })
      toast.success(s === 'open' ? 'Anomaly reopened' : s === 'reviewed' ? 'Marked as reviewed' : 'Anomaly dismissed')
      dataChanged()
      reload()
    } catch (e) { toast.error(errorMessage(e)) }
  }

  const c = data?.counts
  return (
    <div className="animate-fade-up">
      <PageHeader title="Anomalies" subtitle={`Unusual activity worth a look · ${periodLabel(filter)}`} actions={<PeriodPicker />} />

      <div className="mb-5 flex gap-3 rounded-2xl border border-navy-500/15 bg-[#EEF2F8] p-4 text-sm text-ink-soft">
        <Info className="mt-0.5 h-5 w-5 shrink-0 text-navy-500" />
        <p>{data?.disclaimer || 'Anomalies are automated indicators based on your own spending patterns - not a judgement of fraud.'} {' '}
          Detection sensitivity: <b className="capitalize text-ink">{data?.sensitivity || '…'}</b> · <Link to="/settings" className="font-semibold text-brand-600 hover:underline">change</Link></p>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        {[['Open', c?.open, 'text-ink'], ['High', c?.high, 'text-danger-500'], ['Medium', c?.medium, 'text-warn-500'], ['Low', c?.low, 'text-ink-muted']].map(([l, v, cls]) => (
          <Card key={l} className="p-4"><p className="text-xs font-medium text-ink-muted">{l === 'Open' ? 'Open anomalies' : `${l} severity`}</p><p className={`mt-1 text-2xl font-extrabold ${cls}`}>{v ?? '—'}</p></Card>
        ))}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Segmented value={status} onChange={setStatus} options={[{ value: 'open', label: 'Open' }, { value: 'reviewed', label: 'Reviewed' }, { value: 'dismissed', label: 'Dismissed' }, { value: 'all', label: 'All' }]} />
        <label className="ml-auto flex items-center gap-2 text-sm text-ink-muted"><SlidersHorizontal className="h-4 w-4" />
          <select className="select w-auto py-2" value={severity} onChange={(e) => setSeverity(e.target.value)} aria-label="Severity">
            <option value="">All severities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
          </select>
        </label>
      </div>

      {error ? <Card className="card-pad"><ErrorState message={error} onRetry={reload} /></Card> : loading && !data ? <Card className="card-pad"><LoadingBlock rows={8} /></Card> : data.items.length === 0 ? (
        <Card className="card-pad"><EmptyState icon={ShieldCheck} title={status === 'open' ? 'Nothing unusual found' : 'No anomalies here'} message={status === 'open' ? 'Your spending in this period looks consistent with your usual patterns.' : 'Try a different filter.'} /></Card>
      ) : (
        <div className="space-y-3">{data.items.map((a) => <AnomalyCard key={a.key} a={a} onReview={review} />)}</div>
      )}
    </div>
  )
}
