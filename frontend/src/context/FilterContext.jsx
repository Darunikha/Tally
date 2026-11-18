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
  const [accounts, setAccounts] = useState([])
  const [filter, setFilter] = useState({ mode: 'month', month: null, year: null, start: '', end: '', uploadId: '', accountId: '' })
  const [ready, setReady] = useState(false)
  const [version, setVersion] = useState(0) // bump to make pages refetch after data changes

  const refreshMeta = useCallback(async () => {
    if (!user) return
    const [p, s, a] = await Promise.all([api.get('/analytics/periods'), api.get('/analytics/statements-filter'), api.get('/accounts')])
    setPeriods(p.data)
    setStatements(s.data)
    setAccounts(a.data.accounts)
    setFilter((f) => {
      // each check applies on its own: fixing a stale month must not skip clearing a stale statement or account
      let next = f
      const stillValid = f.month && p.data.months.some((m) => m.month === f.month && m.year === f.year)
      if (f.mode === 'month' && !stillValid) {
        const [ty, tm] = p.data.today.split('-').map(Number)
        next = p.data.latest ? { ...next, month: p.data.latest.month, year: p.data.latest.year } : { ...next, month: tm, year: ty }
      }
      if (f.uploadId && !s.data.some((x) => x.id === f.uploadId)) next = { ...next, uploadId: '' }
      if (f.accountId && f.accountId !== 'none' && !a.data.accounts.some((x) => x.id === f.accountId)) next = { ...next, accountId: '' }
      return next
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
    if (filter.accountId) p.account_id = filter.accountId
    return p
  }, [filter])

  const value = useMemo(() => ({ filter, setFilter, params, periods, statements, accounts, ready, version, dataChanged }),
    [filter, params, periods, statements, accounts, ready, version, dataChanged])
  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>
}

export const useFilters = () => useContext(FilterContext)
