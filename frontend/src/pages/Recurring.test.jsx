import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, tokenStore } from '../api/client'
import { FilterProvider } from '../context/FilterContext'
import { renderWithProviders } from '../test/utils'
import Recurring, { amountText, dueText } from './Recurring'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }
})

const item = (o) => ({
  merchant: 'Netflix', category: 'Subscriptions', category_color: '#A07AA8', group: 'subscription', cadence: 'monthly',
  amount_kind: 'fixed', amount: 649, last_amount: 649, occurrences: 4, first_date: '2025-07-07', last_date: '2025-10-07',
  next_expected: '2025-11-07', due_in_days: 7, status: 'active', monthly_cost: 649, yearly_cost: 7788, price_change: null,
  history: [], ignored: false, ...o,
})

const ITEMS = [
  item({ merchant: 'Suresh Nair', category: 'Rent', group: 'bill', amount: 18000, monthly_cost: 18000, next_expected: '2025-11-05', due_in_days: 5 }),
  item({ merchant: 'Netflix', price_change: { from: 649, to: 799, percent: 23.1 }, amount: 799, monthly_cost: 799 }),
  item({ merchant: 'BESCOM', category: 'Bills & Utilities', group: 'bill', amount_kind: 'variable', amount: 1238, monthly_cost: 1238, next_expected: '2025-11-12', due_in_days: 12 }),
  item({ merchant: 'Groww', category: 'Investments', group: 'other', amount: 5000, monthly_cost: 5000, next_expected: '2025-11-16', due_in_days: 16 }),
  item({ merchant: 'Old Gym', group: 'other', category: 'Other', amount: 1500, monthly_cost: 1500, status: 'lapsed', last_date: '2025-04-05', next_expected: '2025-05-05', due_in_days: -179 }),
  item({ merchant: 'Hidden Co', ignored: true, amount: 100, monthly_cost: 100 }),
]
const upcoming = [
  { merchant: 'Suresh Nair', amount: 18000, date: '2025-11-05', due_in_days: 5, amount_kind: 'fixed', category_color: '#EDA100' },
  { merchant: 'BESCOM', amount: 1238, date: '2025-11-12', due_in_days: 12, amount_kind: 'variable', category_color: '#6250D6' },
]
const DATA = {
  as_of: '2025-10-31', items: ITEMS, ignored_count: 1,
  summary: { active_count: 4, lapsed_count: 1, monthly_total: 24686, yearly_total: 296232, upcoming_total: 19238, upcoming, price_changes: 1 },
}

function renderPage(data = DATA) {
  tokenStore.set('test-token') // the filter context only loads for a signed-in user
  api.get.mockImplementation((url) => {
    if (url === '/auth/me') return Promise.resolve({ data: { id: 'u1', full_name: 'Dee', email: 'dee@example.com' } })
    if (url === '/analytics/periods') return Promise.resolve({ data: { months: [], latest: null, today: '2026-11-18' } })
    if (url === '/analytics/statements-filter') return Promise.resolve({ data: [] })
    if (url === '/accounts') return Promise.resolve({ data: { accounts: [], unassigned: null, totals: {} } })
    if (url === '/recurring') return data instanceof Error ? Promise.reject(data) : Promise.resolve({ data })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
  api.put.mockResolvedValue({ data: {} })
  return renderWithProviders(<FilterProvider><Recurring /></FilterProvider>, { route: '/recurring' })
}

const list = () => screen.getByRole('list', { name: 'Recurring payments' })

beforeEach(() => {
  sessionStorage.clear()
  for (const m of [api.get, api.post, api.patch, api.put, api.delete]) m.mockReset()
})

describe('helpers', () => {
  it('words relative dates both ways', () => {
    expect(dueText(0)).toBe('today')
    expect(dueText(1)).toBe('in 1 day')
    expect(dueText(12)).toBe('in 12 days')
    expect(dueText(-1)).toBe('1 day ago')
    expect(dueText(-5)).toBe('5 days ago')
  })
  it('marks varying amounts with a tilde', () => {
    expect(amountText({ amount_kind: 'variable', amount: 1238 })).toBe('~₹1,238')
    expect(amountText({ amount_kind: 'fixed', amount: 649 })).toBe('₹649')
  })
})

describe('Recurring page', () => {
  it('summarises what you are committed to', async () => {
    renderPage()
    expect(await screen.findByText('Monthly commitments')).toBeInTheDocument()
    expect(screen.getByText('₹24,686')).toBeInTheDocument()
    expect(screen.getByText('₹2,96,232')).toBeInTheDocument() // Indian digit grouping
    expect(screen.getByText(/Based on your statements up to 31 Oct 2025/)).toBeInTheDocument()
  })

  it('lists the next 30 days with amounts and a total', async () => {
    renderPage()
    const up = await screen.findByRole('list', { name: 'Upcoming payments' })
    const rows = within(up).getAllByRole('listitem')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('Suresh Nair')
    expect(rows[0]).toHaveTextContent('5 Nov · in 5 days')
    expect(rows[0]).toHaveTextContent('₹18,000')
    expect(rows[1]).toHaveTextContent('~₹1,238') // a varying bill is an estimate
    expect(screen.getByText('₹19,238')).toBeInTheDocument()
  })

  it('hides stopped and hidden payments by default', async () => {
    renderPage()
    await screen.findByRole('list', { name: 'Recurring payments' })
    expect(list()).toHaveTextContent('Suresh Nair')
    expect(list()).not.toHaveTextContent('Old Gym')
    expect(list()).not.toHaveTextContent('Hidden Co')
  })

  it('explains a price change and a varying amount in words', async () => {
    renderPage()
    await screen.findByRole('list', { name: 'Recurring payments' })
    expect(list()).toHaveTextContent('Price up 23.1% (₹649 → ₹799)')
    const bescom = within(list()).getAllByRole('listitem').find((li) => li.textContent.includes('BESCOM'))
    expect(bescom).toHaveTextContent('~₹1,238')
    expect(bescom).toHaveTextContent('Monthly')
  })

  it('filters by group', async () => {
    renderPage()
    await screen.findByRole('list', { name: 'Recurring payments' })
    await userEvent.click(screen.getByRole('tab', { name: 'Subscriptions' }))
    expect(list()).toHaveTextContent('Netflix')
    expect(list()).not.toHaveTextContent('Suresh Nair')
    await userEvent.click(screen.getByRole('tab', { name: 'Bills & rent' }))
    expect(list()).toHaveTextContent('Suresh Nair')
    expect(list()).toHaveTextContent('BESCOM')
    expect(list()).not.toHaveTextContent('Netflix')
    await userEvent.click(screen.getByRole('tab', { name: 'Other' }))
    expect(list()).toHaveTextContent('Groww')
  })

  it('shows payments not seen lately only when asked', async () => {
    renderPage()
    await screen.findByRole('list', { name: 'Recurring payments' })
    await userEvent.click(screen.getByRole('checkbox', { name: /Show not seen lately \(1\)/ }))
    const gym = within(list()).getAllByRole('listitem').find((li) => li.textContent.includes('Old Gym'))
    expect(gym).toHaveTextContent('Not seen lately')
    expect(gym).toHaveTextContent('₹1,500 / month when active') // no misleading "next payment" for a stopped one
    expect(gym).not.toHaveTextContent('Next ')
  })

  it('hides a payment that is not really recurring', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Netflix is not recurring' }))
    expect(api.put).toHaveBeenCalledWith('/recurring/ignored', { merchant: 'Netflix', ignored: true })
    await waitFor(() => expect(api.get.mock.calls.filter(([u]) => u === '/recurring').length).toBeGreaterThan(1)) // list reloads
  })

  it('restores a hidden payment', async () => {
    renderPage()
    await screen.findByRole('list', { name: 'Recurring payments' })
    await userEvent.click(screen.getByRole('button', { name: 'Hidden (1)' }))
    expect(list()).toHaveTextContent('Hidden Co')
    expect(list()).not.toHaveTextContent('Suresh Nair')
    await userEvent.click(screen.getByRole('button', { name: 'Restore Hidden Co' }))
    expect(api.put).toHaveBeenCalledWith('/recurring/ignored', { merchant: 'Hidden Co', ignored: false })
  })

  it('returns to the normal list after restoring the last hidden payment', async () => {
    renderPage()
    await screen.findByRole('list', { name: 'Recurring payments' })
    await userEvent.click(screen.getByRole('button', { name: 'Hidden (1)' }))
    // after the restore the server reports nothing hidden any more
    const restored = { ...DATA, ignored_count: 0, items: ITEMS.map((i) => ({ ...i, ignored: false })) }
    api.get.mockImplementation((url) => {
      if (url === '/recurring') return Promise.resolve({ data: restored })
      if (url === '/auth/me') return Promise.resolve({ data: { id: 'u1', full_name: 'Dee', email: 'dee@example.com' } })
      if (url === '/analytics/periods') return Promise.resolve({ data: { months: [], latest: null, today: '2026-11-18' } })
      return Promise.resolve({ data: [] })
    })
    await userEvent.click(screen.getByRole('button', { name: 'Restore Hidden Co' }))
    await waitFor(() => expect(list()).toHaveTextContent('Suresh Nair'))
    expect(screen.queryByText('Nothing hidden')).not.toBeInTheDocument()
  })

  it('guides you when nothing has been found yet', async () => {
    renderPage({ as_of: null, items: [], ignored_count: 0, summary: { active_count: 0, lapsed_count: 0, monthly_total: 0, yearly_total: 0, upcoming_total: 0, upcoming: [], price_changes: 0 } })
    expect(await screen.findByText('No recurring payments found yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /upload a statement/i })).toHaveAttribute('href', '/upload')
  })

  it('shows an error with retry when loading fails', async () => {
    renderPage(new Error('Server down'))
    expect(await screen.findByText("Couldn't load this")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
