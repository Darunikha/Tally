import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, ArrowRight, Building2, CheckCircle2, CloudUpload, Copy, Eye, EyeOff, FileSpreadsheet, FileText,
  KeyRound, Loader2, LockKeyhole, ShieldCheck, Sparkles, X,
} from 'lucide-react'
import { api, errorMessage } from '../api/client'
import AccountSelect from '../components/AccountSelect'
import { Badge, Card, CardHeader, CategoryPill, PageHeader, TypeBadge } from '../components/ui'
import { useFilters } from '../context/FilterContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { formatBytes, formatDate, formatDateTime, formatINR } from '../lib/format'

const MAX_MB = 10
const EXTENSIONS = ['csv', 'pdf', 'xls', 'xlsx']
const ACCEPT = '.csv,.pdf,.xls,.xlsx,text/csv,application/pdf,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
const PASSWORD_ERRORS = ['pdf_password_required', 'pdf_password_incorrect']
const extOf = (name = '') => name.split('.').pop().toLowerCase()
const FORMAT_LABELS = { generic: 'Other bank (generic parser)', generic_card: 'Other credit card' }
const formatLabel = (b) => FORMAT_LABELS[b.key] || b.bank_name
const isCard = (b) => b.account_type === 'credit_card'

function Step({ n, label, state }) {
  const cls = state === 'done' ? 'bg-brand-500 text-white' : state === 'active' ? 'bg-brand-100 text-brand-700 ring-2 ring-brand-300' : 'bg-canvas text-ink-faint ring-1 ring-line'
  return (
    <div className="flex items-center gap-2">
      <span className={`grid h-7 w-7 place-items-center rounded-full text-xs font-bold ${cls}`}>{state === 'done' ? <CheckCircle2 className="h-4 w-4" /> : n}</span>
      <span className={`text-sm font-semibold ${state === 'pending' ? 'text-ink-faint' : 'text-ink'}`}>{label}</span>
    </div>
  )
}

function Stat({ label, value, sub }) {
  return (
    <div className="rounded-xl bg-canvas px-4 py-3">
      <p className="text-xs font-medium text-ink-muted">{label}</p>
      <p className="mt-0.5 text-lg font-extrabold text-ink">{value}</p>
      {sub && <p className="text-xs text-ink-muted">{sub}</p>}
    </div>
  )
}

export default function Upload() {
  const toast = useToast()
  const { dataChanged } = useFilters()
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [bank, setBank] = useState('')
  const [drag, setDrag] = useState(false)
  const [phase, setPhase] = useState('select') // select | uploading | processing | preview | importing | done
  const [progress, setProgress] = useState(0)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [includeDup, setIncludeDup] = useState(false)
  const [accountId, setAccountId] = useState('') // the account this statement is filed under (chosen at review)
  const [password, setPassword] = useState('') // in memory only; cleared once the file is unlocked
  const [showPw, setShowPw] = useState(false)
  const pwRef = useRef(null)
  const isPdf = !!file && extOf(file.name) === 'pdf'
  const needsPassword = PASSWORD_ERRORS.includes(error?.code)

  useEffect(() => { if (needsPassword) pwRef.current?.focus() }, [needsPassword, error])
  const banks = useApi('/statements/banks')
  const history = useApi('/statements', null, [result])

  const pick = (f) => {
    setError(null)
    if (!f) return
    if (!EXTENSIONS.includes(extOf(f.name))) return setError({ message: 'Only CSV, PDF and Excel (.xls, .xlsx) statements are supported.' })
    if (f.size > MAX_MB * 1024 * 1024) return setError({ message: `File is larger than ${MAX_MB} MB.` })
    if (f.size === 0) return setError({ message: 'The selected file is empty.' })
    setFile(f)
    setPassword(''); setShowPw(false)
  }

  const reset = () => {
    setFile(null); setPreview(null); setResult(null); setError(null); setProgress(0); setPhase('select'); setIncludeDup(false); setAccountId('')
    setPassword(''); setShowPw(false)
    if (inputRef.current) inputRef.current.value = ''
  }

  const upload = async () => {
    setPhase('uploading'); setProgress(0); setError(null)
    const form = new FormData()
    form.append('file', file)
    if (bank) form.append('bank', bank)
    if (isPdf && password) form.append('password', password)
    try {
      const r = await api.post('/statements/preview', form, {
        onUploadProgress: (e) => {
          const p = e.total ? Math.round((e.loaded / e.total) * 100) : 50
          setProgress(p)
          if (p >= 100) setPhase('processing')
        },
      })
      setPreview(r.data)
      setAccountId(r.data.suggested_account_id || '')
      setPassword('') // no longer needed once the statement is unlocked
      setPhase('preview')
    } catch (e) {
      setError({ message: errorMessage(e), code: e.response?.data?.error?.code, details: e.response?.data?.error?.details })
      setPhase('select')
    }
  }

  const confirm = async () => {
    setPhase('importing')
    try {
      const r = await api.post(`/statements/${preview.upload.id}/confirm`, { include_duplicates: includeDup, ...(accountId ? { account_id: accountId } : {}) })
      setResult(r.data)
      setPhase('done')
      toast.success(`${r.data.transaction_count} transactions imported`, 'Statement imported')
      dataChanged()
    } catch (e) {
      toast.error(errorMessage(e))
      setPhase('preview')
    }
  }

  const cancel = async () => {
    if (preview) await api.delete(`/statements/${preview.upload.id}/preview`).catch(() => {})
    reset()
  }

  const up = preview?.upload
  const stepState = (i) => {
    const order = { select: 0, uploading: 0, processing: 1, preview: 1, importing: 2, done: 3 }[phase]
    return i < order ? 'done' : i === order ? 'active' : 'pending'
  }

  return (
    <div className="animate-fade-up">
      <PageHeader title="Upload Statement" subtitle="Import a CSV, PDF or Excel statement. You'll review everything before it's saved." />

      <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-3">
        <Step n={1} label="Choose file" state={stepState(0)} />
        <span className="hidden h-px w-8 bg-line sm:block" />
        <Step n={2} label="Review" state={stepState(1)} />
        <span className="hidden h-px w-8 bg-line sm:block" />
        <Step n={3} label="Import" state={stepState(2)} />
      </div>

      {(phase === 'select' || phase === 'uploading' || phase === 'processing') && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <Card className="card-pad">
            <div
              onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]) }}
              onClick={() => phase === 'select' && inputRef.current?.click()}
              role="button" tabIndex={0} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition ${
                drag ? 'border-brand-400 bg-brand-50' : 'border-line bg-canvas/50 hover:border-brand-300 hover:bg-brand-50/40'}`}>
              <div className="mb-4 grid h-16 w-16 place-items-center rounded-2xl bg-white text-brand-500 shadow-card"><CloudUpload className="h-8 w-8" /></div>
              <p className="text-base font-bold text-ink">Drag & drop your statement here</p>
              <p className="mt-1 text-sm text-ink-muted">or <span className="font-semibold text-brand-600">browse files</span> · CSV, PDF or Excel · up to {MAX_MB} MB</p>
              <input ref={inputRef} type="file" accept={ACCEPT} className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
            </div>

            {file && (
              <div className="mt-5 flex items-center gap-3 rounded-xl border border-line p-3">
                <span className="grid h-10 w-10 place-items-center rounded-lg bg-brand-50 text-brand-600">{isPdf ? <FileText className="h-5 w-5" /> : <FileSpreadsheet className="h-5 w-5" />}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink">{file.name}</p>
                  <p className="text-xs text-ink-muted">{formatBytes(file.size)}</p>
                  {phase !== 'select' && (
                    <div className="mt-2">
                      <div className="h-1.5 overflow-hidden rounded-full bg-canvas"><div className={`h-full rounded-full bg-brand-500 transition-all ${phase === 'processing' ? 'animate-pulse' : ''}`} style={{ width: `${progress}%` }} /></div>
                      <p className="mt-1 text-xs text-ink-muted">{phase === 'uploading' ? `Uploading… ${progress}%` : 'Reading statement, detecting bank and categorising…'}</p>
                    </div>
                  )}
                </div>
                {phase === 'select' && <button className="rounded-lg p-1.5 text-ink-faint hover:bg-canvas hover:text-ink" onClick={reset} aria-label="Remove file"><X className="h-4 w-4" /></button>}
              </div>
            )}

            {error && !needsPassword && (
              <div role="alert" className="mt-5 flex gap-3 rounded-xl bg-danger-50 p-4 text-sm">
                <AlertTriangle className="h-5 w-5 shrink-0 text-danger-500" />
                <div>
                  <p className="font-semibold text-danger-600">{error.code === 'duplicate_statement' ? 'Already imported' : 'Upload failed'}</p>
                  <p className="text-ink-soft">{error.message}</p>
                  {error.code === 'duplicate_statement' && <Link to="/statements" className="mt-1 inline-block font-semibold text-brand-600 hover:underline">View statement history</Link>}
                  {error.code === 'parse_error' && <p className="mt-1 text-ink-muted">Tip: choose your bank or card explicitly below, or export the statement as CSV or Excel from net banking.</p>}
                </div>
              </div>
            )}

            {isPdf && phase === 'select' && (
              <div className={`mt-5 rounded-xl p-4 transition ${needsPassword ? 'bg-warn-50 ring-1 ring-warn-100' : 'bg-canvas'}`}>
                {needsPassword && (
                  <div role="alert" className="mb-3 flex gap-2.5 text-sm">
                    <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-warn-500" />
                    <div>
                      <p className="font-semibold text-ink">{error.code === 'pdf_password_incorrect' ? 'Incorrect password' : 'This statement is password protected'}</p>
                      <p className="text-ink-soft">{error.message}</p>
                    </div>
                  </div>
                )}
                <label className="label flex items-center gap-1.5" htmlFor="pdf-pw"><KeyRound className="h-3.5 w-3.5" />PDF password {!needsPassword && <span className="font-normal normal-case tracking-normal text-ink-faint">(only if the file is locked)</span>}</label>
                <div className="relative">
                  <input id="pdf-pw" ref={pwRef} type={showPw ? 'text' : 'password'} className="input pr-11" maxLength={128}
                    autoComplete="off" spellCheck={false} value={password} placeholder="e.g. date of birth or customer ID"
                    onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && password && upload()} />
                  <button type="button" onClick={() => setShowPw((v) => !v)} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-ink-muted hover:bg-white hover:text-ink" aria-label={showPw ? 'Hide password' : 'Show password'}>
                    {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <p className="mt-1.5 text-xs text-ink-muted">Banks usually use your date of birth (DDMMYYYY), customer ID, or part of your name + birth date - check the email the statement came with. The password is only used to open this file and is never stored.</p>
              </div>
            )}

            <div className="mt-5 flex flex-wrap items-end gap-3">
              <div className="min-w-[14rem] flex-1">
                <label className="label" htmlFor="bank">Statement format</label>
                <select id="bank" className="select" value={bank} onChange={(e) => setBank(e.target.value)} disabled={phase !== 'select'}>
                  <option value="">Auto-detect (recommended)</option>
                  <optgroup label="Bank accounts">
                    {(banks.data || []).filter((b) => !isCard(b)).map((b) => <option key={b.key} value={b.key}>{formatLabel(b)}</option>)}
                  </optgroup>
                  <optgroup label="Credit cards">
                    {(banks.data || []).filter(isCard).map((b) => <option key={b.key} value={b.key}>{formatLabel(b)}</option>)}
                  </optgroup>
                </select>
              </div>
              <button className="btn-primary h-[42px]" disabled={!file || phase !== 'select' || (needsPassword && !password)} onClick={upload}>
                {phase !== 'select' ? <Loader2 className="h-4 w-4 animate-spin" /> : needsPassword ? <LockKeyhole className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
                {needsPassword ? 'Unlock & analyse' : 'Analyse statement'}
              </button>
            </div>
          </Card>

          <div className="space-y-6">
            <Card className="card-pad">
              <CardHeader icon={Building2} title="Supported formats" />
              <ul className="space-y-2 text-sm text-ink-soft">
                {(banks.data || []).filter((b) => !isCard(b) && b.key !== 'generic').map((b) => <li key={b.key} className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-brand-500" />{b.bank_name} <span className="text-xs text-ink-faint">CSV · PDF · Excel</span></li>)}
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-brand-500" />Other banks via the generic parser</li>
                {(banks.data || []).some(isCard) && <li className="flex items-start gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" /><span>Credit cards: {(banks.data || []).filter((b) => isCard(b) && b.key !== 'generic_card').map((b) => b.bank_name.replace(' Credit Card', '')).join(', ')} and other issuers <span className="text-xs text-ink-faint">CSV · PDF · Excel</span></span></li>}
              </ul>
              <p className="mt-3 text-xs text-ink-muted">CSV, Excel (.xls/.xlsx) and text PDFs - including password-protected e-statements - work out of the box. Scanned PDFs need OCR (Tesseract) on the server.</p>
            </Card>
            <Card className="card-pad">
              <CardHeader icon={ShieldCheck} title="Your data, handled carefully" />
              <ul className="space-y-2 text-sm text-ink-soft">
                <li>• Files are processed in memory and never stored.</li>
                <li>• PDF passwords are used once to unlock the file, never saved.</li>
                <li>• Nothing is imported until you confirm.</li>
                <li>• No bank logins, no payments - read-only analysis.</li>
                <li>• Statement data is never sent to external AI services.</li>
              </ul>
            </Card>
          </div>
        </div>
      )}

      {(phase === 'preview' || phase === 'importing') && up && (
        <div className="space-y-6">
          <Card className="card-pad">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm text-ink-muted">Detected</p>
                <h2 className="flex flex-wrap items-center gap-2 text-xl font-extrabold text-ink">{up.bank_name}{up.account_type === 'credit_card' && <Badge tone="navy">Credit card</Badge>}</h2>
                <p className="text-xs text-ink-muted">{up.file_name} · parser <code className="rounded bg-canvas px-1">{up.parser_used}</code></p>
                {up.account_type === 'credit_card' && <p className="mt-1 max-w-xl text-xs text-ink-muted">Purchases count as spending. Payments you make to the card are filed under Credit Card Payments and are not counted as income.</p>}
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="btn-secondary" onClick={cancel} disabled={phase === 'importing'}>Cancel</button>
                <button className="btn-primary" onClick={confirm} disabled={phase === 'importing' || (preview.new_count === 0 && !includeDup)}>
                  {phase === 'importing' ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                  Import {includeDup ? up.parsed_count : preview.new_count} transactions
                </button>
              </div>
            </div>
            <div className="mb-4 max-w-md">
              <label className="label" htmlFor="account">Account</label>
              <AccountSelect id="account" value={accountId} onChange={setAccountId} accountType={up.account_type} bankName={up.bank_name}
                disabled={phase === 'importing'} noneLabel="Don't file under an account" />
              <p className="mt-1.5 text-xs text-ink-muted">
                {preview.suggested_account_id && accountId === preview.suggested_account_id ? 'Matched to your account for this bank. ' : ''}
                Filing statements under accounts lets you see each account's balance and spending on its own. You can change it later in Statement History.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
              <Stat label="Transactions found" value={up.parsed_count} />
              <Stat label="New" value={preview.new_count} />
              <Stat label="Duplicates" value={up.duplicate_count} sub="already imported" />
              <Stat label="Period" value={`${formatDate(up.date_range.start, { year: false })} – ${formatDate(up.date_range.end, { year: false })}`} sub={up.date_range.end?.slice(0, 4)} />
              <Stat label="Debits (new)" value={formatINR(up.total_debits)} />
              <Stat label="Credits (new)" value={formatINR(up.total_credits)} />
            </div>
            {(up.warnings?.length > 0 || preview.uncategorized_count > 0 || up.duplicate_count > 0) && (
              <div className="mt-4 space-y-2">
                {up.warnings.map((w) => <p key={w} className="flex items-start gap-2 rounded-xl bg-warn-50 px-3 py-2 text-sm text-ink-soft"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn-500" />{w}</p>)}
                {preview.uncategorized_count > 0 && <p className="flex items-start gap-2 rounded-xl bg-canvas px-3 py-2 text-sm text-ink-soft"><Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />{preview.uncategorized_count} transaction(s) didn't match any rule and will be marked <b>Other</b> for review.</p>}
                {up.duplicate_count > 0 && (
                  <label className="flex cursor-pointer items-start gap-2 rounded-xl bg-canvas px-3 py-2 text-sm text-ink-soft">
                    <input type="checkbox" className="mt-0.5 accent-brand-500" checked={includeDup} onChange={(e) => setIncludeDup(e.target.checked)} />
                    <span><Copy className="mr-1 inline h-3.5 w-3.5" />{up.duplicate_count} transaction(s) match ones you've already imported and will be skipped. Tick to import them anyway.</span>
                  </label>
                )}
              </div>
            )}
          </Card>

          <Card className="overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4">
              <h3 className="font-bold text-ink">Preview</h3>
              <p className="text-xs text-ink-muted">Showing {preview.transactions.length} of {up.parsed_count}</p>
            </div>
            <div className="scrollbar-thin max-h-[32rem] overflow-auto">
              <table className="w-full min-w-[760px]">
                <thead className="sticky top-0 bg-canvas"><tr>
                  <th className="table-th">Date</th><th className="table-th">Merchant</th><th className="table-th">Category</th>
                  <th className="table-th">Method</th><th className="table-th text-right">Amount</th><th className="table-th">Status</th>
                </tr></thead>
                <tbody className="divide-y divide-line">
                  {preview.transactions.map((t) => (
                    <tr key={t.id} className={t.is_duplicate ? 'opacity-50' : ''}>
                      <td className="table-td whitespace-nowrap text-ink-soft">{formatDate(t.transaction_date)}</td>
                      <td className="table-td max-w-[18rem]"><p className="truncate font-semibold text-ink">{t.normalized_merchant}</p><p className="truncate text-xs text-ink-muted" title={t.raw_description}>{t.raw_description}</p></td>
                      <td className="table-td"><CategoryPill name={t.category_name} color={t.category_color} /></td>
                      <td className="table-td text-ink-soft">{t.payment_method}</td>
                      <td className={`table-td whitespace-nowrap text-right font-semibold ${t.transaction_type === 'credit' ? 'text-brand-600' : 'text-ink'}`}>{t.transaction_type === 'credit' ? '+' : ''}{formatINR(t.amount, { decimals: true })}</td>
                      <td className="table-td">{t.is_duplicate ? <Badge tone="warn">Duplicate</Badge> : t.needs_review ? <Badge>Review</Badge> : <TypeBadge type={t.transaction_type} />}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {phase === 'done' && result && (
        <Card className="card-pad">
          <div className="flex flex-col items-center py-8 text-center">
            <div className="mb-4 grid h-16 w-16 place-items-center rounded-full bg-brand-50 text-brand-500"><CheckCircle2 className="h-9 w-9" /></div>
            <h2 className="text-xl font-extrabold text-ink">Statement imported</h2>
            <p className="mt-1 text-sm text-ink-muted">{result.transaction_count} transactions from {result.bank_name} were added{result.account_id ? ' to your account' : ''}{result.duplicate_count ? `, ${result.duplicate_count} duplicates skipped` : ''}.</p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              <Link to="/" className="btn-primary">Go to dashboard<ArrowRight className="h-4 w-4" /></Link>
              <Link to={`/transactions?upload_id=${result.id}`} className="btn-secondary">View transactions</Link>
              <button className="btn-ghost" onClick={reset}>Upload another</button>
            </div>
          </div>
        </Card>
      )}

      {history.data?.length > 0 && phase === 'select' && (
        <Card className="card-pad mt-6">
          <CardHeader title="Recent uploads" action={<Link to="/statements" className="text-sm font-semibold text-brand-600 hover:underline">Full history</Link>} />
          <ul className="divide-y divide-line">
            {history.data.slice(0, 5).map((h) => (
              <li key={h.id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                <FileText className="h-4 w-4 text-ink-muted" />
                <span className="min-w-0 flex-1 truncate font-medium text-ink">{h.file_name}</span>
                <span className="text-ink-muted">{h.bank_name || '—'}</span>
                <span className="text-ink-muted">{formatDateTime(h.upload_date)}</span>
                {h.processing_status === 'completed' ? <Badge tone="brand">{h.transaction_count} txns</Badge> : <Badge tone="danger">Failed</Badge>}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
