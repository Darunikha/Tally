const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const inr2 = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const num = new Intl.NumberFormat('en-IN')

export const formatINR = (v, { decimals = false } = {}) => (v == null || Number.isNaN(v) ? '—' : (decimals ? inr2 : inr).format(v))
export const formatNumber = (v) => (v == null ? '—' : num.format(v))

/** Compact Indian notation for axes: 1.2K, 3.4L, 1.1Cr */
export function compactINR(v) {
  const a = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(a >= 1e8 ? 0 : 1)}Cr`
  if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(a >= 1e6 ? 0 : 1)}L`
  if (a >= 1e3) return `${sign}₹${(a / 1e3).toFixed(a >= 1e4 ? 0 : 1)}K`
  return `${sign}₹${Math.round(a)}`
}

const TZ = 'Asia/Kolkata'
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** "2025-10-17" -> "17 Oct 2025" (calendar dates; no timezone shifting) */
export function formatDate(iso, { year = true } = {}) {
  if (!iso) return '—'
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return `${d} ${MONTHS[m - 1]}${year ? ' ' + y : ''}`
}

/** Timestamps (UTC ISO) shown in IST */
export function formatDateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-IN', { timeZone: TZ, day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function istHour() {
  return Number(new Date().toLocaleString('en-US', { timeZone: TZ, hour: 'numeric', hour12: false }))
}

export function greeting() {
  const h = istHour()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

export const pct = (v, digits = 0) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(digits)}%`)

export function formatBytes(b) {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 / 1024).toFixed(1)} MB`
}

export const initials = (name = '') => name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('') || 'U'

export const firstName = (name = '') => name.trim().split(/\s+/)[0] || 'there'
