import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, CloudUpload, ShieldCheck, Sparkles } from 'lucide-react'
import { Modal } from '../ui'
import DemoDataButton from './DemoDataButton'

const STEPS = [
  {
    icon: CloudUpload, title: 'Bring in a statement',
    body: 'Download a statement from your bank or credit card app and upload it here. CSV, Excel and PDF all work, including password-protected e-statements from HDFC, ICICI, SBI, Axis, Kotak and more.',
  },
  {
    icon: Sparkles, title: 'Tally does the sorting',
    body: 'It recognises UPI merchants, sorts every transaction into a category you can change, keeps track of subscriptions and bills, and flags anything that looks unusual. You stay in control of the rules.',
  },
  {
    icon: ShieldCheck, title: 'Private by design',
    body: 'Tally only reads files you give it. It never connects to your bank, never moves money, and never sends your statements to outside AI services. Uploaded files are not kept.',
  },
]

/** Three short screens shown once to a new user. Every way out marks it as seen, so it never returns. */
export default function WelcomeTour({ firstName, onFinish }) {
  const navigate = useNavigate()
  const [i, setI] = useState(0)
  const last = i === STEPS.length - 1
  const { icon: Icon, title, body } = STEPS[i]

  return (
    <Modal open onClose={() => onFinish()} title={`Welcome to Tally${firstName ? `, ${firstName}` : ''}`} size="md"
      footer={(
        <div className="flex w-full flex-wrap items-center gap-2">
          <button className="btn-ghost btn-sm" onClick={() => onFinish()}>Skip for now</button>
          <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
            {i > 0 && <button className="btn-secondary" onClick={() => setI(i - 1)}><ChevronLeft className="h-4 w-4" />Back</button>}
            {!last && <button className="btn-primary" onClick={() => setI(i + 1)}>Next<ChevronRight className="h-4 w-4" /></button>}
            {last && <DemoDataButton onLoaded={() => onFinish()} />}
            {last && <button className="btn-primary" onClick={() => { onFinish(); navigate('/upload') }}><CloudUpload className="h-4 w-4" />Upload a statement</button>}
          </div>
        </div>
      )}>
      <div className="flex flex-col items-center py-4 text-center">
        <div className="mb-4 grid h-16 w-16 place-items-center rounded-2xl bg-brand-50 text-brand-600"><Icon className="h-8 w-8" /></div>
        <h2 className="text-lg font-extrabold text-ink">{title}</h2>
        <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-soft">{body}</p>
        <div className="mt-5 flex items-center gap-2" role="group" aria-label={`Step ${i + 1} of ${STEPS.length}`}>
          {STEPS.map((s, k) => (
            <button key={s.title} onClick={() => setI(k)} aria-label={`Go to step ${k + 1}: ${s.title}`} aria-current={k === i ? 'step' : undefined}
              className={`h-2 rounded-full transition-all ${k === i ? 'w-6 bg-brand-solid' : 'w-2 bg-brand-200 hover:bg-brand-300'}`} />
          ))}
        </div>
      </div>
    </Modal>
  )
}
