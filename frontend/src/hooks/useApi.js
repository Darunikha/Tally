import { useCallback, useEffect, useRef, useState } from 'react'
import { api, cleanParams, errorMessage } from '../api/client'

/**
 * GET with loading/error state. Refetches when `url` or serialized `params` change, or `deps` change.
 * Pass url=null to wait (reported as loading).
 */
export function useApi(url, params, deps = []) {
  const [data, setData] = useState(null)
  // `loading` stays true until the first response, including while url is still null (waiting on deps)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const key = JSON.stringify(cleanParams(params))
  const reqId = useRef(0)

  const load = useCallback(async () => {
    if (!url) return
    const id = ++reqId.current
    setLoading(true)
    setError(null)
    try {
      const r = await api.get(url, { params: JSON.parse(key) })
      if (id === reqId.current) setData(r.data)
    } catch (e) {
      if (id === reqId.current) setError(errorMessage(e))
    } finally {
      if (id === reqId.current) setLoading(false)
    }
  }, [url, key])

  useEffect(() => { load() }, [load, ...deps]) // eslint-disable-line react-hooks/exhaustive-deps
  return { data, loading, error, reload: load, setData }
}
