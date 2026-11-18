import { useState } from 'react'
import { Loader2, Sparkles } from 'lucide-react'
import { api, errorMessage } from '../../api/client'
import { useFilters } from '../../context/FilterContext'
import { useToast } from '../../context/ToastContext'

/** Loads the bundled synthetic statements so a new user can look around before uploading their own. */
export default function DemoDataButton({ className = 'btn-secondary', label = 'Try with demo data', onLoaded }) {
  const toast = useToast()
  const { dataChanged } = useFilters()
  const [busy, setBusy] = useState(false)

  const load = async () => {
    setBusy(true)
    try {
      const r = (await api.post('/settings/demo-data')).data
      const n = (r.imported || []).reduce((sum, f) => sum + (f.transactions || 0), 0)
      toast.success(n ? `${n.toLocaleString('en-IN')} sample transactions loaded. You can remove them in Settings.` : 'Demo data is already loaded.', 'Demo data ready')
      await dataChanged()
      onLoaded?.()
    } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }

  return (
    <button className={className} onClick={load} disabled={busy}>
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}{busy ? 'Loading…' : label}
    </button>
  )
}
