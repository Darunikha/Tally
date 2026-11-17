import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, LockKeyhole, ShieldCheck, Sparkles, Zap } from 'lucide-react'
import { errorMessage } from '../api/client'
import { Logo } from '../components/layout/Sidebar'
import { useAuth } from '../context/AuthContext'

function Shell({ title, subtitle, children, footer }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <div className="relative hidden overflow-hidden bg-brand-800 p-12 text-white lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-[radial-gradient(40rem_25rem_at_0%_0%,rgba(140,197,162,0.35),transparent),radial-gradient(30rem_20rem_at_100%_100%,rgba(61,90,128,0.5),transparent)]" />
        <div className="relative flex items-center gap-2.5">
          <svg viewBox="0 0 32 32" className="h-9 w-9"><path d="M6 26C6 13 15 6 27 5c0 13-8 21-20 21H6Z" fill="#8CC5A2" /><path d="M7 25 18 14" stroke="#173F2B" strokeWidth="2" strokeLinecap="round" /></svg>
          <span className="text-2xl font-extrabold">Spendly</span>
        </div>
        <div className="relative my-auto max-w-md">
          <h2 className="text-4xl font-extrabold leading-tight tracking-tight">Understand every rupee, from every statement.</h2>
          <p className="mt-4 text-brand-100/90">Upload bank statements from any bank. Spendly reads them, recognises UPI merchants, categorises spending and flags anything unusual.</p>
          <ul className="mt-8 space-y-4 text-sm">
            {[[Zap, 'Works with HDFC, ICICI, SBI, Axis, Kotak and generic CSV/PDF formats'],
              [Sparkles, 'Automatic categorisation with rules you control'],
              [ShieldCheck, 'Read-only: no bank logins, no payments, no third-party AI']].map(([I, t]) => (
              <li key={t} className="flex items-start gap-3"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/10"><I className="h-4 w-4" /></span><span className="pt-1.5 text-brand-50">{t}</span></li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-brand-100/70">Your data stays on the server you run.</p>
      </div>
      <div className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-sm animate-fade-up">
          <Logo className="mb-8 lg:hidden" />
          <h1 className="text-2xl font-extrabold tracking-tight text-ink">{title}</h1>
          <p className="mt-1 text-sm text-ink-muted">{subtitle}</p>
          <div className="mt-8">{children}</div>
          <p className="mt-6 text-center text-sm text-ink-muted">{footer}</p>
        </div>
      </div>
    </div>
  )
}

function Field({ id, label, ...props }) {
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <input id={id} className="input h-11" {...props} />
    </div>
  )
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
    <Shell title="Welcome back" subtitle="Sign in to see your spending." footer={<>New to Spendly? <Link to="/register" className="font-semibold text-brand-600 hover:underline">Create an account</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <Field id="email" label="Email" type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <Field id="password" label="Password" type="password" autoComplete="current-password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        {error && <p role="alert" className="rounded-xl bg-danger-50 px-3 py-2 text-sm text-danger-600">{error}</p>}
        <button className="btn-primary h-11 w-full" disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LockKeyhole className="h-4 w-4" />}Sign in</button>
      </form>
    </Shell>
  )
}

export function Register() {
  const { register } = useAuth()
  const [form, setForm] = useState({ full_name: '', email: '', password: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try { await register(form) } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }
  return (
    <Shell title="Create your account" subtitle="Start analysing your statements in a minute." footer={<>Already have an account? <Link to="/login" className="font-semibold text-brand-600 hover:underline">Sign in</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <Field id="name" label="Full name" autoComplete="name" required maxLength={80} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        <Field id="email" label="Email" type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <div>
          <Field id="password" label="Password" type="password" autoComplete="new-password" required minLength={8} maxLength={72} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <p className="mt-1.5 text-xs text-ink-muted">At least 8 characters, with letters and numbers.</p>
        </div>
        {error && <p role="alert" className="rounded-xl bg-danger-50 px-3 py-2 text-sm text-danger-600">{error}</p>}
        <button className="btn-primary h-11 w-full" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Create account</button>
      </form>
    </Shell>
  )
}
