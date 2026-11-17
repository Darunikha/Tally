/** Local-calendar date helpers (statement dates are calendar dates, no timezone maths needed). */
export function add(date, { days = 0, months = 0 } = {}) {
  const d = new Date(date)
  if (months) d.setMonth(d.getMonth() + months)
  if (days) d.setDate(d.getDate() + days)
  return d
}

export function toISO(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
