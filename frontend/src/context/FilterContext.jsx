import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from './AuthContext'

/**
 * Global period + statement filter shared by Dashboard, Analytics, UPI and Anomalies.
 * mode: 'month' (month+year) | 'year' | 'all' | 'custom' (start/end)
 */
const FilterContext = createContext(null)

export function FilterProvider({ children }) {
  const { user } = useAuth()
  const [periods, setPeriods] = useState({ months: [], latest: null })
  const [statements, setStatements] = useState([])
  const [filter, setFilter] = useState({ mode: 'month', month: null, year: null, start: '', end: '', uploadId: '' })
  const [ready, setReady] = useState(false)
  const [version, setVersion] = useState(0) // bump to make pages refetch after data changes

  const refreshMeta = useCallback(async () => {
    if (!user) return
    const [p, s] = await Promise.all([api.get('/analytics/periods'), api.get('/analytics/statements-filter')])
    setPeriods(p.data)
    setStatements(s.data)
    setFilter((f) => {
      const stillValid = f.month && p.data.months.some((m) => m.month === f.month && m.year === f.year)
      if (f.mode === 'month' && !stillValid) {
        if (p.data.latest) return { ...f, month: p.data.latest.month, year: p.data.latest.year }
        const [y, m] = p.data.today.split('-').map(Number)
        return { ...f, month: m, year: y }
      }
      if (f.uploadId && !s.data.some((x) => x.id === f.uploadId)) return { ...f, uploadId: '' }
      return f
    })
    setReady(true)
  }, [user])

  useEffect(() => { refreshMeta().catch(() => setReady(true)) }, [refreshMeta])

  const dataChanged = useCallback(async () => {
    await refreshMeta().catch(() => {})
    setVersion((v) => v + 1)
  }, [refreshMeta])

  /** Query params understood by every analytics endpoint. */
  const params = useMemo(() => {
    const p = {}
    if (filter.mode === 'month' && filter.month) { p.month = filter.month; p.year = filter.year }
    if (filter.mode === 'year' && filter.year) p.year = filter.year
    if (filter.mode === 'custom') { if (filter.start) p.start = filter.start; if (filter.end) p.end = filter.end }
    if (filter.uploadId) p.upload_id = filter.uploadId
    return p
  }, [filter])

  const value = useMemo(() => ({ filter, setFilter, params, periods, statements, ready, version, dataChanged }),
    [filter, params, periods, statements, ready, version, dataChanged])
  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>
}

export const useFilters = () => useContext(FilterContext)
