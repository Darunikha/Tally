import { useEffect, useState } from 'react'
import { AlertTriangle, Database, KeyRound, Loader2, ShieldCheck, Sparkles, User } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import { Card, CardHeader, ConfirmDialog, PageHeader, Segmented } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useFilters } from '../context/FilterContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'

export default function SettingsPage() {
  const toast = useToast()
  const { user, setUser, logout } = useAuth()
  const { dataChanged, version } = useFilters()
  const summary = useApi('/settings/data-summary', null, [version])
  const [profile, setProfile] = useState({ full_name: '', anomaly_sensitivity: 'medium', threshold: '' })
  const [pw, setPw] = useState({ current_password: '', new_password: '', confirm: '' })
  const [busy, setBusy] = useState('')
  const [confirm, setConfirm] = useState(null)
  const [delPassword, setDelPassword] = useState('')

  useEffect(() => {
    if (user) setProfile({ full_name: user.full_name, anomaly_sensitivity: user.settings?.anomaly_sensitivity || 'medium', threshold: user.settings?.large_transaction_threshold ?? '' })
  }, [user])

  const run = async (key, fn) => {
    setBusy(key)
    try { await fn() } catch (e) { toast.error(errorMessage(e)) } finally { setBusy('') }
  }

  const saveProfile = () => run('profile', async () => {
    const body = { full_name: profile.full_name.trim(), anomaly_sensitivity: profile.anomaly_sensitivity }
    if (profile.threshold === '' || profile.threshold === null) body.clear_large_threshold = true
    else body.large_transaction_threshold = Number(profile.threshold)
    const r = await api.patch('/settings/profile', body)
    setUser(r.data)
    toast.success('Settings saved')
    dataChanged()
  })

  const changePassword = () => run('pw', async () => {
    if (pw.new_password !== pw.confirm) throw { response: { data: { error: { message: 'New passwords do not match' } } } }
    await api.post('/settings/password', { current_password: pw.current_password, new_password: pw.new_password })
    setPw({ current_password: '', new_password: '', confirm: '' })
    toast.success('Password changed')
  })

  const demo = (load) => run('demo', async () => {
    if (load) {
      const r = await api.post('/settings/demo-data')
      const n = r.data.imported.reduce((s, x) => s + x.transactions, 0)
      toast.success(r.data.imported.length ? `${n} synthetic transactions imported` : 'Demo data is already loaded', 'Demo data')
    } else {
      const r = await api.delete('/settings/demo-data')
      toast.success(`${r.data.deleted_transactions} demo transactions removed`)
    }
    dataChanged()
  })

  const doConfirm = () => run('confirm', async () => {
    if (confirm === 'data') {
      await api.delete('/settings/data')
      toast.success('All statements and transactions deleted')
      dataChanged()
    } else {
      await api.delete('/settings/account', { data: { password: delPassword } })
      logout()
    }
    setConfirm(null)
  })

  const s = summary.data
  return (
    <div className="animate-fade-up">
      <PageHeader title="Settings" subtitle="Profile, security, detection preferences and your data." />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card className="card-pad">
          <CardHeader icon={User} title="Profile & preferences" />
          <div className="space-y-4">
            <div><label className="label" htmlFor="s-name">Full name</label><input id="s-name" className="input" maxLength={80} value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} /></div>
            <div><label className="label" htmlFor="s-email">Email</label><input id="s-email" className="input bg-canvas" value={user?.email || ''} disabled /></div>
            <div>
              <span className="label">Anomaly detection sensitivity</span>
              <Segmented value={profile.anomaly_sensitivity} onChange={(v) => setProfile({ ...profile, anomaly_sensitivity: v })} options={[{ value: 'low', label: 'Low' }, { value: 'medium', label: 'Medium' }, { value: 'high', label: 'High' }]} />
              <p className="mt-1.5 text-xs text-ink-muted">Higher sensitivity flags smaller deviations from your usual spending.</p>
            </div>
            <div>
              <label className="label" htmlFor="s-th">Large transaction alert (₹)</label>
              <input id="s-th" type="number" min={0} className="input" placeholder="Off" value={profile.threshold} onChange={(e) => setProfile({ ...profile, threshold: e.target.value })} />
              <p className="mt-1.5 text-xs text-ink-muted">Always flag debits at or above this amount. Leave empty to turn off.</p>
            </div>
            <p className="text-xs text-ink-muted">Currency: Indian Rupee (₹) · Time zone: Asia/Kolkata</p>
            <button className="btn-primary" onClick={saveProfile} disabled={busy === 'profile' || !profile.full_name.trim()}>{busy === 'profile' && <Loader2 className="h-4 w-4 animate-spin" />}Save changes</button>
          </div>
        </Card>

        <Card className="card-pad">
          <CardHeader icon={KeyRound} title="Change password" />
          <div className="space-y-4">
            <div><label className="label" htmlFor="pw-c">Current password</label><input id="pw-c" type="password" autoComplete="current-password" className="input" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></div>
            <div><label className="label" htmlFor="pw-n">New password</label><input id="pw-n" type="password" autoComplete="new-password" minLength={8} maxLength={72} className="input" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></div>
            <div><label className="label" htmlFor="pw-r">Confirm new password</label><input id="pw-r" type="password" autoComplete="new-password" className="input" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} /></div>
            <button className="btn-primary" onClick={changePassword} disabled={busy === 'pw' || !pw.current_password || pw.new_password.length < 8}>{busy === 'pw' && <Loader2 className="h-4 w-4 animate-spin" />}Update password</button>
          </div>
          <div className="mt-6 flex gap-3 rounded-xl bg-brand-50/70 p-4 text-sm text-ink-soft">
            <ShieldCheck className="h-5 w-5 shrink-0 text-brand-600" />
            <p>Tally is read-only: it never connects to your bank, never stores bank credentials and never initiates payments. Uploaded files are processed in memory and discarded.</p>
          </div>
        </Card>

        <Card className="card-pad">
          <CardHeader icon={Sparkles} title="Demo mode" subtitle="Explore Tally with a synthetic statement" />
          <p className="text-sm text-ink-soft">Imports a bundled, fully synthetic HDFC-format statement (Aug–Oct 2025) through the real parsing pipeline. It contains no real customer information.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button className="btn-primary" onClick={() => demo(true)} disabled={busy === 'demo' || s?.demo_available === false}>{busy === 'demo' && <Loader2 className="h-4 w-4 animate-spin" />}Load demo data</button>
            <button className="btn-secondary" onClick={() => demo(false)} disabled={busy === 'demo' || !s?.demo_statements}>Remove demo data</button>
          </div>
        </Card>

        <Card className="card-pad">
          <CardHeader icon={Database} title="Your data" />
          {s && (
            <dl className="mb-5 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              {[['Statements', s.statements], ['Transactions', s.transactions], ['Custom rules', s.custom_rules], ['Custom categories', s.custom_categories]].map(([k, v]) => (
                <div key={k} className="rounded-xl bg-canvas p-3"><dt className="text-xs text-ink-muted">{k}</dt><dd className="text-lg font-extrabold text-ink">{v.toLocaleString('en-IN')}</dd></div>
              ))}
            </dl>
          )}
          <div className="space-y-3 rounded-xl border border-danger-100 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div><p className="text-sm font-semibold text-ink">Delete all statements & transactions</p><p className="text-xs text-ink-muted">Keeps your account, categories and rules.</p></div>
              <button className="btn-secondary text-danger-500" onClick={() => setConfirm('data')}>Delete data</button>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-danger-100 pt-3">
              <div><p className="text-sm font-semibold text-ink">Delete account</p><p className="text-xs text-ink-muted">Permanently removes your account and everything in it.</p></div>
              <button className="btn-danger" onClick={() => { setDelPassword(''); setConfirm('account') }}>Delete account</button>
            </div>
          </div>
        </Card>
      </div>

      <ConfirmDialog open={!!confirm} danger busy={busy === 'confirm'} onClose={() => setConfirm(null)} onConfirm={doConfirm}
        title={confirm === 'account' ? 'Delete your account?' : 'Delete all data?'} confirmLabel={confirm === 'account' ? 'Delete account' : 'Delete everything'}
        message={confirm === 'account' ? 'Your account, statements, transactions, categories and rules will be permanently deleted.' : 'All statements and transactions will be permanently deleted. This cannot be undone.'}>
        {confirm === 'account' && (
          <div className="mt-4">
            <label className="label" htmlFor="del-pw"><AlertTriangle className="mr-1 inline h-3 w-3" />Confirm with your password</label>
            <input id="del-pw" type="password" className="input" value={delPassword} onChange={(e) => setDelPassword(e.target.value)} autoComplete="current-password" />
          </div>
        )}
      </ConfirmDialog>
    </div>
  )
}
