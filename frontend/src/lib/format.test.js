import { afterEach, describe, expect, it, vi } from 'vitest'
import { compactINR, firstName, formatBytes, formatDate, formatINR, greeting, initials, pct } from './format'
import { add, toISO } from './dates'

describe('formatINR', () => {
  it('uses Indian digit grouping and the rupee sign', () => {
    expect(formatINR(1234567)).toBe('₹12,34,567')
    expect(formatINR(85000)).toBe('₹85,000')
  })
  it('keeps paise only when asked', () => {
    expect(formatINR(250.5, { decimals: true })).toBe('₹250.50')
    expect(formatINR(250.5)).toBe('₹251')
  })
  it('shows a dash for missing values', () => {
    expect(formatINR(null)).toBe('—')
    expect(formatINR(undefined)).toBe('—')
    expect(formatINR(NaN)).toBe('—')
  })
})

describe('compactINR (chart axes)', () => {
  it.each([
    [0, '₹0'], [950, '₹950'], [1500, '₹1.5K'], [45000, '₹45K'], [150000, '₹1.5L'],
    [2500000, '₹25L'], [12000000, '₹1.2Cr'], [-1500, '-₹1.5K'],
  ])('%s -> %s', (v, out) => expect(compactINR(v)).toBe(out))
})

describe('formatDate', () => {
  it('formats calendar dates without timezone shifts', () => {
    expect(formatDate('2025-10-17')).toBe('17 Oct 2025')
    expect(formatDate('2025-01-01T00:00:00Z')).toBe('1 Jan 2025')
    expect(formatDate('2025-12-31', { year: false })).toBe('31 Dec')
  })
  it('handles empty input', () => expect(formatDate(null)).toBe('—'))
})

describe('small helpers', () => {
  it('pct adds a sign', () => {
    expect(pct(18.04)).toBe('+18%')
    expect(pct(-3.5, 1)).toBe('-3.5%')
    expect(pct(null)).toBe('—')
  })
  it('initials and first name', () => {
    expect(initials('Darunikha Sharma')).toBe('DS')
    expect(initials('')).toBe('U')
    expect(firstName('  Darunikha Sharma ')).toBe('Darunikha')
    expect(firstName('')).toBe('there')
  })
  it('formatBytes', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(6656)).toBe('6.5 KB')
    expect(formatBytes(3 * 1024 * 1024)).toBe('3.0 MB')
  })
  it('date helpers', () => {
    expect(toISO(add(new Date(2025, 9, 31), { months: -1 }))).toBe('2025-10-01') // JS month rollover is explicit
    expect(toISO(add(new Date(2025, 9, 1), { days: 30 }))).toBe('2025-10-31')
  })
})

describe('greeting uses India time', () => {
  afterEach(() => vi.useRealTimers())
  it.each([
    ['2025-10-17T02:30:00Z', 'Good morning'],   // 08:00 IST
    ['2025-10-17T08:30:00Z', 'Good afternoon'], // 14:00 IST
    ['2025-10-17T13:30:00Z', 'Good evening'],   // 19:00 IST
  ])('%s -> %s', (utc, expected) => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(utc))
    expect(greeting()).toBe(expected)
  })
})
