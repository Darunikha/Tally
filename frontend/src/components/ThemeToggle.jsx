import { useEffect, useRef, useState } from 'react'
import { Check, Monitor, Moon, Sun } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'

const CHOICES = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'Match device', icon: Monitor },
]

/** Header button that opens a small menu: Light, Dark or Match device. */
export default function ThemeToggle() {
  const { preference, resolved, setPreference } = useTheme()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const away = (e) => { if (!ref.current?.contains(e.target)) setOpen(false) }
    const esc = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', away)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', away); document.removeEventListener('keydown', esc) }
  }, [open])

  const Current = resolved === 'dark' ? Moon : Sun
  const label = CHOICES.find((c) => c.value === preference).label
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open} aria-label={`Theme: ${label}`}
        className="grid h-11 w-11 place-items-center rounded-full text-ink-soft transition hover:bg-surface">
        <Current className="h-5 w-5" />
      </button>
      {open && (
        <div role="menu" aria-label="Theme" className="absolute right-0 z-40 mt-2 w-48 rounded-2xl border border-line bg-surface p-1.5 shadow-pop animate-fade-up">
          {CHOICES.map(({ value, label: l, icon: Icon }) => (
            <button key={value} role="menuitemradio" aria-checked={preference === value}
              onClick={() => { setPreference(value); setOpen(false) }}
              className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm text-ink-soft hover:bg-canvas">
              <Icon className="h-4 w-4" />
              <span className="flex-1">{l}</span>
              {preference === value && <Check className="h-4 w-4 text-brand-600" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
