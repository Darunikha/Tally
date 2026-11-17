import axios from 'axios'

const TOKEN_KEY = 'spendly_token'

export const tokenStore = {
  get: () => { try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null } },
  set: (t) => { try { sessionStorage.setItem(TOKEN_KEY, t) } catch { /* storage unavailable */ } },
  clear: () => { try { sessionStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ } },
}

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api', timeout: 60000 })

api.interceptors.request.use((config) => {
  const t = tokenStore.get()
  if (t) config.headers.Authorization = `Bearer ${t}`
  return config
})

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401 && !error.config?.url?.startsWith('/auth/')) onUnauthorized()
    return Promise.reject(error)
  },
)

/** Human-readable message from an API error response. */
export function errorMessage(err, fallback = 'Something went wrong') {
  const e = err?.response?.data?.error
  if (e?.code === 'validation_error' && Array.isArray(e.details) && e.details.length) {
    return e.details.map((d) => `${d.field ? d.field + ': ' : ''}${d.message}`).join('; ')
  }
  if (e?.message) return e.message
  if (err?.code === 'ECONNABORTED') return 'The request timed out'
  if (!err?.response) return 'Cannot reach the server - is the API running?'
  return fallback
}

/** Drop empty values so they are not sent as query params. */
export function cleanParams(obj) {
  return Object.fromEntries(Object.entries(obj || {}).filter(([, v]) => v !== '' && v !== null && v !== undefined))
}
