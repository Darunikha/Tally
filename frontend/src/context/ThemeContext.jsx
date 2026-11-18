import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

export const THEME_KEY = 'tally_theme'
export const THEME_CHOICES = ['light', 'dark', 'system']
const PAGE_COLOR = { light: '#F6F6F1', dark: '#0E1411' } // the browser's address bar / status bar on phones

function readPreference() {
  try {
    const v = localStorage.getItem(THEME_KEY)
    return THEME_CHOICES.includes(v) ? v : 'system'
  } catch { return 'system' } // storage can be blocked (private windows)
}
const darkQuery = () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null)

// Outside a provider (an isolated component in a test, say) behave as plain light mode.
const ThemeContext = createContext({ preference: 'light', resolved: 'light', setPreference: () => {} })

/**
 * Light, dark, or follow the device. The choice is remembered in this browser only. index.html applies it before the
 * first paint, so a dark-mode user never sees a flash of the light page.
 */
export function ThemeProvider({ children }) {
  const [preference, setPreferenceState] = useState(readPreference)
  const [systemDark, setSystemDark] = useState(() => !!darkQuery()?.matches)

  useEffect(() => {
    const mq = darkQuery()
    if (!mq) return undefined
    const onChange = (e) => setSystemDark(e.matches)
    mq.addEventListener?.('change', onChange)
    return () => mq.removeEventListener?.('change', onChange)
  }, [])

  const resolved = preference === 'system' ? (systemDark ? 'dark' : 'light') : preference

  useEffect(() => {
    document.documentElement.classList.toggle('dark', resolved === 'dark')
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', PAGE_COLOR[resolved])
  }, [resolved])

  const setPreference = useCallback((p) => {
    if (!THEME_CHOICES.includes(p)) return
    setPreferenceState(p)
    try {
      if (p === 'system') localStorage.removeItem(THEME_KEY)
      else localStorage.setItem(THEME_KEY, p)
    } catch { /* the choice still applies for this visit */ }
  }, [])

  const value = useMemo(() => ({ preference, resolved, setPreference }), [preference, resolved, setPreference])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export const useTheme = () => useContext(ThemeContext)
