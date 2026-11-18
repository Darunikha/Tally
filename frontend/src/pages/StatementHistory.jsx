import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CloudUpload, Eye, FileSpreadsheet, FileText, History, Trash2 } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import AccountSelect from '../components/AccountSelect'
import { Badge, Card, ConfirmDialog, EmptyState, ErrorState, LoadingBlock, PageHeader } from '../components/ui'
import { useFilters } from '../context/FilterContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { formatBytes, formatDate, formatDateTime, formatINR } from '../lib/format'

const STATUS = { completed: ['brand', 'Imported'], failed: ['danger', 'Failed'], deleting: ['warn', 'Deleting'] }

export default function StatementHistory() {
  const toast = useToast()
  const navigate = useNavigate()
  const { dataChanged, setFilter } = useFilters()
  const { data, loading, error, reload } = useApi('/statements')
  const [del, setDel] = useState(null)
  const [busy, setBusy] = useState(false)

  const remove = async () => {
    setBusy(true)
    try {
      const r = await api.delete(`/statements/${del.id}`)
      toast.success(`${r.data.deleted_transactions} transactions removed`, 'Statement deleted')
      setDel(null); reload(); dataChanged()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }

  const moveTo = async (s, accountId) => {
    try {
      await api.put(`/statements/${s.id}/account`, { account_id: accountId || null })
      toast.success(accountId ? 'Statement moved' : 'Statement is no longer filed under an account')
      reload(); dataChanged()
    } catch (e) { toast.error(errorMessage(e)) }
  }

  const viewOnDashboard = (s) => {
    setFilter((f) => ({ ...f, mode: 'all', uploadId: s.id, accountId: '' }))
    navigate('/')
  }

  return (
    <div className="animate-fade-up">
      <PageHeader title="Statement History" subtitle="Every statement you've uploaded, with its import results."
        actions={<Link to="/upload" className="btn-primary"><CloudUpload className="h-4 w-4" />Upload statement</Link>} />
      <Card className="overflow-hidden">
        {error ? <ErrorState message={error} onRetry={reload} /> : loading && !data ? <div className="p-6"><LoadingBlock rows={6} /></div> : data.length === 0 ? (
          <EmptyState icon={History} title="No statements yet" message="Uploaded statements and their import results will appear here." action={<Link to="/upload" className="btn-primary">Upload your first statement</Link>} />
        ) : (
          <div className="scrollbar-thin overflow-x-auto">
            <table className="w-full min-w-[1100px]">
              <thead className="bg-canvas/70"><tr>
                <th className="table-th">File</th><th className="table-th">Bank</th><th className="table-th">Account</th><th className="table-th">Uploaded</th><th className="table-th">Period</th>
                <th className="table-th text-right">Transactions</th><th className="table-th text-right">Debits</th><th className="table-th text-right">Credits</th><th className="table-th">Status</th><th className="table-th" />
              </tr></thead>
              <tbody className="divide-y divide-line">
                {data.map((s) => {
                  const [tone, label] = STATUS[s.processing_status] || ['neutral', s.processing_status]
                  return (
                    <tr key={s.id} className="hover:bg-canvas/60">
                      <td className="table-td max-w-[16rem]">
                        <div className="flex items-center gap-3">
                          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">{s.file_type === 'pdf' ? <FileText className="h-4 w-4" /> : <FileSpreadsheet className="h-4 w-4" />}</span>
                          <div className="min-w-0"><p className="truncate font-semibold text-ink">{s.file_name}</p><p className="text-xs text-ink-muted">{s.file_type.toUpperCase()} · {formatBytes(s.file_size)}{s.is_demo ? ' · demo' : ''}</p></div>
                        </div>
                      </td>
                      <td className="table-td text-ink-soft">{s.bank_name || '—'}{s.account_type === 'credit_card' && <> <Badge tone="navy">Credit card</Badge></>}<p className="text-xs text-ink-faint">{s.parser_used}</p></td>
                      <td className="table-td min-w-[11rem]">
                        {s.processing_status === 'completed'
                          ? <AccountSelect id={`acct-${s.id}`} value={s.account_id || ''} accountType={s.account_type || 'bank'} bankName={s.bank_name}
                              noneLabel="Not filed" onChange={(v) => moveTo(s, v)} />
                          : <span className="text-ink-faint">—</span>}
                      </td>
                      <td className="table-td whitespace-nowrap text-ink-soft">{formatDateTime(s.upload_date)}</td>
                      <td className="table-td whitespace-nowrap text-ink-soft">{s.date_range?.start ? `${formatDate(s.date_range.start)} – ${formatDate(s.date_range.end)}` : '—'}</td>
                      <td className="table-td text-right font-semibold">{s.transaction_count}{s.duplicate_count > 0 && <p className="text-xs font-normal text-ink-muted">{s.duplicate_count} duplicates skipped</p>}</td>
                      <td className="table-td text-right">{formatINR(s.total_debits)}</td>
                      <td className="table-td text-right text-brand-600">{formatINR(s.total_credits)}</td>
                      <td className="table-td"><Badge tone={tone}>{label}</Badge>{s.error && <p className="mt-1 max-w-[12rem] text-xs text-danger-500">{s.error}</p>}</td>
                      <td className="table-td">
                        <div className="flex justify-end gap-1">
                          {s.processing_status === 'completed' && <>
                            <Link to={`/transactions?upload_id=${s.id}`} className="rounded-lg p-1.5 max-sm:p-2.5 text-ink-muted hover:bg-canvas hover:text-ink" title="View transactions" aria-label="View transactions"><Eye className="h-4 w-4" /></Link>
                            <button onClick={() => viewOnDashboard(s)} className="btn-ghost btn-sm">Dashboard</button>
                          </>}
                          <button className="rounded-lg p-1.5 max-sm:p-2.5 text-ink-muted hover:bg-danger-50 hover:text-danger-500" onClick={() => setDel(s)} title="Delete statement" aria-label="Delete statement"><Trash2 className="h-4 w-4" /></button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <ConfirmDialog open={!!del} danger busy={busy} onClose={() => setDel(null)} onConfirm={remove} title="Delete this statement?" confirmLabel="Delete statement"
        message={del ? `“${del.file_name}” and its ${del.transaction_count} transactions will be permanently removed. Analytics will be recalculated. This cannot be undone.` : ''} />
    </div>
  )
}
