import { useState } from 'react'
import { FileDown, Loader2 } from 'lucide-react'
import { errorMessage } from '../api/client'
import { useToast } from '../context/ToastContext'
import { downloadFile } from '../lib/download'

/** PDF spending report for the period (and statement) currently chosen in the global filter. */
export default function DownloadReportButton({ params }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const run = async () => {
    setBusy(true)
    try {
      const name = await downloadFile('/reports/summary.pdf', params, 'tally-report.pdf')
      toast.success(`Downloaded ${name}`)
    } catch (e) { toast.error(errorMessage(e, 'Could not create the report')) } finally { setBusy(false) }
  }
  return (
    <button className="btn-secondary h-11 rounded-xl shadow-sm" onClick={run} disabled={busy} title="Download a PDF report for this period">
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileDown className="h-4 w-4 text-ink-soft" />}
      <span className="hidden sm:inline">{busy ? 'Preparing…' : 'Report'}</span>
      <span className="sr-only sm:hidden">Download report</span>
    </button>
  )
}
