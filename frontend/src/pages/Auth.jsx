import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCircle2, KeyRound, Loader2, LockKeyhole, MailCheck, ShieldCheck, Sparkles, XCircle, Zap } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import { Logo } from '../components/layout/Sidebar'
import { useAuth } from '../context/AuthContext'

function LegalLinks() {
  return (
    <p className="mt-8 text-center text-xs text-ink-faint">
      <Link to="/privacy" className="hover:text-ink-soft hover:underline">Privacy Policy</Link>
      <span className="mx-2">·</span>
      <Link to="/terms" className="hover:text-ink-soft hover:underline">Terms of Service</Link>
    </p>
  )
}

export function Shell({ title, subtitle, children, footer }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <div className="relative hidden overflow-hidden bg-brand-800 p-12 text-white lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-[radial-gradient(40rem_25rem_at_0%_0%,rgba(140,197,162,0.35),transparent),radial-gradient(30rem_20rem_at_100%_100%,rgba(61,90,128,0.5),transparent)]" />
        <div className="relative flex items-center gap-2.5">
          <svg viewBox="0 0 32 32" className="h-9 w-9"><path d="M6 26C6 13 15 6 27 5c0 13-8 21-20 21H6Z" fill="#8CC5A2" /><path d="M7 25 18 14" stroke="#173F2B" strokeWidth="2" strokeLinecap="round" /></svg>
          <span className="text-2xl font-extrabold">Tally</span>
        </div>
        <div className="relative my-auto max-w-md">
          <h2 className="text-4xl font-extrabold leading-tight tracking-tight">Understand every rupee, from every statement.</h2>
          <p className="mt-4 text-white/85">Upload bank statements from any bank. Tally reads them, recognises UPI merchants, categorises spending and flags anything unusual.</p>
          <ul className="mt-8 space-y-4 text-sm">
            {[[Zap, 'Works with HDFC, ICICI, SBI, Axis, Kotak and other banks - CSV, Excel or PDF'],
              [Sparkles, 'Automatic categorisation with rules you control'],
              [ShieldCheck, 'Read-only: no bank logins, no payments, no third-party AI']].map(([I, t]) => (
              <li key={t} className="flex items-start gap-3"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/10"><I className="h-4 w-4" /></span><span className="pt-1.5 text-brand-50">{t}</span></li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-white/65">Your data stays on the server you run.</p>
      </div>
      <div className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-sm animate-fade-up">
          <Logo className="mb-8 lg:hidden" />
          <h1 className="text-2xl font-extrabold tracking-tight text-ink">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-ink-muted">{subtitle}</p>}
          <div className="mt-8">{children}</div>
          {footer && <p className="mt-6 text-center text-sm text-ink-muted">{footer}</p>}
          <LegalLinks />
        </div>
      </div>
    </div>
  )
}

function Field({ id, label, hint, ...props }) {
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <input id={id} className="input h-11" {...props} />
      {hint && <p className="mt-1.5 text-xs text-ink-muted">{hint}</p>}
    </div>
  )
}

function Alert({ tone = 'error', children }) {
  const cls = tone === 'error' ? 'bg-danger-50 text-danger-600' : 'bg-brand-50 text-brand-700'
  return <p role="alert" className={`rounded-xl px-3 py-2 text-sm ${cls}`}>{children}</p>
}

export function Login() {
  const { login } = useAuth()
  const [form, setForm] = useState({ email: '', password: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try { await login(form.email, form.password) } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }
  return (
    <Shell title="Welcome back" subtitle="Sign in to see your spending." footer={<>New to Tally? <Link to="/register" className="font-semibold text-brand-600 hover:underline">Create an account</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <Field id="email" label="Email" type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <div>
          <div className="mb-1.5 flex items-baseline justify-between">
            <label htmlFor="password" className="label mb-0">Password</label>
            <Link to={`/forgot-password${form.email ? `?email=${encodeURIComponent(form.email)}` : ''}`} className="text-xs font-semibold text-brand-600 hover:underline">Forgot password?</Link>
          </div>
          <input id="password" className="input h-11" type="password" autoComplete="current-password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </div>
        {error && <Alert>{error}</Alert>}
        <button className="btn-primary h-11 w-full" disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LockKeyhole className="h-4 w-4" />}Sign in</button>
      </form>
    </Shell>
  )
}

export function Register() {
  const { register } = useAuth()
  const [form, setForm] = useState({ full_name: '', email: '', password: '', accept_terms: false })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    if (!form.accept_terms) return setError('Please accept the Terms of Service and Privacy Policy to continue.')
    setBusy(true); setError('')
    try { await register(form) } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }
  return (
    <Shell title="Create your account" subtitle="Start analysing your statements in a minute." footer={<>Already have an account? <Link to="/login" className="font-semibold text-brand-600 hover:underline">Sign in</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <Field id="name" label="Full name" autoComplete="name" required maxLength={80} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        <Field id="email" label="Email" type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
          hint="We'll send a link to confirm it's yours." />
        <Field id="password" label="Password" type="password" autoComplete="new-password" required minLength={8} maxLength={72} value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })} hint="At least 8 characters, with letters and numbers." />
        <label className="flex cursor-pointer items-start gap-2.5 rounded-xl bg-canvas p-3 text-sm text-ink-soft">
          <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-brand-500" checked={form.accept_terms} required
            onChange={(e) => setForm({ ...form, accept_terms: e.target.checked })} />
          <span>I am 18 or older and I agree to the <Link to="/terms" target="_blank" className="font-semibold text-brand-600 hover:underline">Terms of Service</Link> and
            consent to my data being processed as described in the <Link to="/privacy" target="_blank" className="font-semibold text-brand-600 hover:underline">Privacy Policy</Link>.</span>
        </label>
        {error && <Alert>{error}</Alert>}
        <button className="btn-primary h-11 w-full" disabled={busy || !form.accept_terms}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Create account</button>
      </form>
    </Shell>
  )
}

export function ForgotPassword() {
  const [sp] = useSearchParams()
  const [email, setEmail] = useState(sp.get('email') || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try { setSent((await api.post('/auth/forgot-password', { email })).data.message) } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }
  return (
    <Shell title="Reset your password" subtitle="Enter your account email and we'll send you a reset link."
      footer={<>Remembered it? <Link to="/login" className="font-semibold text-brand-600 hover:underline">Back to sign in</Link></>}>
      {sent ? (
        <div className="rounded-2xl border border-brand-100 bg-brand-50 p-5 text-center">
          <MailCheck className="mx-auto h-10 w-10 text-brand-500" />
          <p className="mt-3 font-semibold text-ink">Check your inbox</p>
          <p className="mt-1 text-sm text-ink-soft">{sent}</p>
          <p className="mt-3 text-xs text-ink-muted">Didn't get it? Check spam, or try again in a few minutes.</p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <Field id="email" label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          {error && <Alert>{error}</Alert>}
          <button className="btn-primary h-11 w-full" disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}Send reset link</button>
        </form>
      )}
    </Shell>
  )
}

export function ResetPassword() {
  const [sp] = useSearchParams()
  const token = sp.get('token') || ''
  const navigate = useNavigate()
  const { logout } = useAuth()
  const [form, setForm] = useState({ password: '', confirm: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    if (form.password !== form.confirm) return setError('The passwords do not match.')
    setBusy(true); setError('')
    try {
      const r = await api.post('/auth/reset-password', { token, new_password: form.password })
      logout() // every session was revoked server-side
      setDone(r.data.message)
    } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }
  if (!token) {
    return <Shell title="Link incomplete" subtitle="This reset link is missing its code. Please use the full link from the email, or request a new one."
      footer={<Link to="/forgot-password" className="font-semibold text-brand-600 hover:underline">Request a new link</Link>} />
  }
  return (
    <Shell title="Choose a new password" subtitle="This will sign you out on all devices.">
      {done ? (
        <div className="rounded-2xl border border-brand-100 bg-brand-50 p-5 text-center">
          <CheckCircle2 className="mx-auto h-10 w-10 text-brand-500" />
          <p className="mt-3 font-semibold text-ink">Password updated</p>
          <p className="mt-1 text-sm text-ink-soft">{done}</p>
          <button className="btn-primary mt-4" onClick={() => navigate('/login')}>Sign in</button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <Field id="np" label="New password" type="password" autoComplete="new-password" required minLength={8} maxLength={72}
            value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} hint="At least 8 characters, with letters and numbers." />
          <Field id="cp" label="Confirm new password" type="password" autoComplete="new-password" required value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
          {error && <Alert>{error}{/invalid|expired/i.test(error) && <> <Link to="/forgot-password" className="font-semibold underline">Request a new link</Link></>}</Alert>}
          <button className="btn-primary h-11 w-full" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Update password</button>
        </form>
      )}
    </Shell>
  )
}

export function VerifyEmail() {
  const [sp] = useSearchParams()
  const token = sp.get('token') || ''
  const { user, refreshUser } = useAuth()
  const [state, setState] = useState({ status: token ? 'loading' : 'error', message: token ? '' : 'This verification link is incomplete.' })
  const ran = useRef(false)
  useEffect(() => {
    if (!token || ran.current) return
    ran.current = true // StrictMode runs effects twice; the token is single-use
    api.post('/auth/verify-email', { token })
      .then((r) => { setState({ status: 'ok', message: r.data.message }); refreshUser().catch(() => {}) })
      .catch((e) => setState({ status: 'error', message: errorMessage(e) }))
  }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Shell title="Email verification">
      <div className={`rounded-2xl border p-6 text-center ${state.status === 'error' ? 'border-danger-100 bg-danger-50' : 'border-brand-100 bg-brand-50'}`}>
        {state.status === 'loading' && <><Loader2 className="mx-auto h-10 w-10 animate-spin text-brand-500" /><p className="mt-3 text-sm text-ink-soft">Verifying…</p></>}
        {state.status === 'ok' && <><CheckCircle2 className="mx-auto h-10 w-10 text-brand-500" /><p className="mt-3 font-semibold text-ink">You're verified!</p><p className="mt-1 text-sm text-ink-soft">{state.message}</p></>}
        {state.status === 'error' && <><XCircle className="mx-auto h-10 w-10 text-danger-500" /><p className="mt-3 font-semibold text-ink">Couldn't verify</p><p className="mt-1 text-sm text-ink-soft">{state.message}</p>
          {user && <p className="mt-2 text-xs text-ink-muted">You can request a new link from the banner in the app.</p>}</>}
        {state.status !== 'loading' && <Link to={user ? '/' : '/login'} className="btn-primary mt-5">{user ? 'Go to dashboard' : 'Sign in'}</Link>}
      </div>
    </Shell>
  )
}
