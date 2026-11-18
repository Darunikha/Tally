import { createContext, useCallback, useContext, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

const ToastContext = createContext(null)
let nextId = 1

const STYLES = {
  success: { icon: CheckCircle2, cls: 'text-brand-600' },
  error: { icon: AlertTriangle, cls: 'text-danger-500' },
  info: { icon: Info, cls: 'text-navy-500' },
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), [])
  const push = useCallback((type, message, title) => {
    const id = nextId++
    setToasts((t) => [...t.slice(-3), { id, type, message, title }])
    setTimeout(() => dismiss(id), type === 'error' ? 7000 : 4000)
  }, [dismiss])

  const api = {
    success: (m, t) => push('success', m, t),
    error: (m, t) => push('error', m, t),
    info: (m, t) => push('info', m, t),
  }

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 lg:bottom-6 lg:items-end lg:pr-6" aria-live="polite">
        {toasts.map((t) => {
          const S = STYLES[t.type]
          return (
            <div key={t.id} role="status" className="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border border-line bg-surface px-4 py-3 shadow-pop animate-fade-up">
              <S.icon className={`mt-0.5 h-5 w-5 shrink-0 ${S.cls}`} />
              <div className="min-w-0 flex-1">
                {t.title && <p className="text-sm font-semibold text-ink">{t.title}</p>}
                <p className="text-sm text-ink-soft">{t.message}</p>
              </div>
              <button onClick={() => dismiss(t.id)} className="text-ink-faint hover:text-ink" aria-label="Dismiss"><X className="h-4 w-4" /></button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
