import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, tokenStore } from '../api/client'
import BudgetsCard from '../components/BudgetProgress'
import { FilterProvider } from '../context/FilterContext'
import { renderWithProviders } from '../test/utils'
import Budgets from './Budgets'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }
})

const row = (o) => ({
  id: 'b1', category_id: 'c1', name: 'Food & Dining', color: '#1BAF7A', monthly_limit: 10000, alert_threshold: 80,
  spent: 4000, remaining: 6000, percent: 40, status: 'ok', projected: null, projected_over: false, daily_allowance: null, ...o,
})
const month = { year: 2025, month: 8, label: 'August 2025', is_current: false, days_in_month: 31, days_left: 0 }
const status = (o) => ({
  month, overall: null, budgets: [], unbudgeted: [], suggested_overall: null, total_spent: 0,
  summary: { over: 0, warning: 0, ok: 0 }, ...o,
})
const CATEGORIES = [
  { id: 'c1', name: 'Food & Dining' }, { id: 'c2', name: 'Shopping' }, { id: 'c3', name: 'Income' }, { id: 'c4', name: 'Rent' },
]

function renderPage(budgetStatus, { latest = { year: 2025, month: 8 } } = {}) {
  tokenStore.set('test-token') // the filter context only loads for a signed-in user
  api.get.mockImplementation((url) => {
    if (url === '/auth/me') return Promise.resolve({ data: { id: 'u1', full_name: 'Dee', email: 'dee@example.com' } })
    if (url === '/analytics/periods') return Promise.resolve({ data: { months: latest ? [{ ...latest, label: 'x', transaction_count: 1 }] : [], latest, today: '2026-11-18' } })
    if (url === '/analytics/statements-filter') return Promise.resolve({ data: [] })
    if (url === '/accounts') return Promise.resolve({ data: { accounts: [], unassigned: null, totals: {} } })
    if (url === '/categories') return Promise.resolve({ data: CATEGORIES })
    if (url === '/budgets/status') return budgetStatus instanceof Error ? Promise.reject(budgetStatus) : Promise.resolve({ data: budgetStatus })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
  api.put.mockResolvedValue({ data: {} })
  api.delete.mockResolvedValue({ data: { ok: true } })
  return renderWithProviders(<FilterProvider><Budgets /></FilterProvider>, { route: '/budgets' })
}

const statusCalls = () => api.get.mock.calls.filter(([u]) => u === '/budgets/status').map(([, c]) => c.params)

beforeEach(() => {
  sessionStorage.clear()
  for (const m of [api.get, api.post, api.patch, api.put, api.delete]) m.mockReset()
})

describe('Budgets page - progress', () => {
  it('shows every budget with its status in words, not only colour', async () => {
    renderPage(status({
      overall: row({ id: 'o', category_id: null, name: 'Overall spending', monthly_limit: 30000, spent: 12000, remaining: 18000, percent: 40 }),
      budgets: [
        row({ id: 'b1', name: 'Shopping', monthly_limit: 2000, spent: 2600, remaining: -600, percent: 130, status: 'over' }),
        row({ id: 'b2', name: 'Food & Dining', monthly_limit: 5000, spent: 4200, remaining: 800, percent: 84, status: 'warning' }),
        row({ id: 'b3', name: 'Rent', monthly_limit: 20000, spent: 100, remaining: 19900, percent: 0.5 }),
      ],
      summary: { over: 1, warning: 1, ok: 2 },
    }))
    expect(await screen.findByText('Over budget')).toBeInTheDocument()
    expect(screen.getByText('Nearly there')).toBeInTheDocument()
    expect(screen.getAllByText('On track')).toHaveLength(2)
    expect(screen.getByText('₹600 over')).toBeInTheDocument()
    expect(screen.getByText('₹800 left')).toBeInTheDocument()
    const shopping = screen.getByRole('progressbar', { name: 'Shopping budget' })
    expect(shopping).toHaveAttribute('aria-valuenow', '100') // a bar never overflows its track
    expect(shopping).toHaveAttribute('aria-valuetext', '130% spent, Over budget')
    expect(screen.getByRole('progressbar', { name: 'Overall spending budget' })).toHaveAttribute('aria-valuenow', '40')
  })

  it('explains the daily allowance and an over-pace projection', async () => {
    renderPage(status({
      budgets: [row({ spent: 6000, remaining: 4000, percent: 60, daily_allowance: 400, projected: 14000, projected_over: true })],
    }))
    expect(await screen.findByText(/₹400/)).toBeInTheDocument()
    expect(screen.getByText(/you'll spend about ₹14,000, which is ₹4,000 over/i)).toBeInTheDocument()
  })
})

describe('Budgets page - creating', () => {
  it('starts on the latest month with data and lets you move between months', async () => {
    renderPage(status())
    expect(await screen.findByText('No budgets yet')).toBeInTheDocument()
    expect(statusCalls()[0]).toEqual({ year: 2025, month: 8 })
    await userEvent.click(screen.getByRole('button', { name: 'Previous month' }))
    await waitFor(() => expect(statusCalls().at(-1)).toEqual({ year: 2025, month: 7 }))
    await userEvent.click(screen.getByRole('button', { name: 'Next month' }))
    await userEvent.click(screen.getByRole('button', { name: 'Next month' }))
    await waitFor(() => expect(statusCalls().at(-1)).toEqual({ year: 2025, month: 9 }))
  })

  it('cannot move past the current month', async () => {
    const now = new Date()
    renderPage(status(), { latest: { year: now.getFullYear(), month: now.getMonth() + 1 } })
    await screen.findByText('No budgets yet')
    expect(screen.getByRole('button', { name: 'Next month' })).toBeDisabled()
  })

  it('creates an overall budget prefilled with the suggestion', async () => {
    renderPage(status({ suggested_overall: 25000 }))
    await userEvent.click(await screen.findByRole('button', { name: /set an overall budget/i }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByLabelText(/monthly limit/i)).toHaveValue(25000)
    expect(within(dialog).getByText(/suggested from your average monthly spending: ₹25,000/i)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: /save budget/i }))
    expect(api.put).toHaveBeenCalledWith('/budgets', { category_id: null, monthly_limit: 25000, alert_threshold: 80 })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('sets a budget for a category that has spending but no budget', async () => {
    renderPage(status({ unbudgeted: [{ category_id: 'c2', name: 'Shopping', color: '#EB6834', spent: 1800, suggested_limit: 2000 }] }))
    await userEvent.click(await screen.findByRole('button', { name: 'Set a budget for Shopping' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByLabelText('Category')).toHaveValue('c2')
    expect(within(dialog).getByLabelText(/monthly limit/i)).toHaveValue(2000)
    await userEvent.selectOptions(within(dialog).getByLabelText(/warn me at/i), '90')
    await userEvent.click(within(dialog).getByRole('button', { name: /save budget/i }))
    expect(api.put).toHaveBeenCalledWith('/budgets', { category_id: 'c2', monthly_limit: 2000, alert_threshold: 90 })
  })

  it('only offers categories that do not have a budget yet (and never Income)', async () => {
    renderPage(status({ budgets: [row({ category_id: 'c1' })] }))
    await userEvent.click(await screen.findByRole('button', { name: /add budget/i }))
    const options = within(screen.getByLabelText('Category')).getAllByRole('option').map((o) => o.textContent)
    expect(options).toEqual(['Overall spending (all categories)', 'Shopping', 'Rent'])
  })

  it('will not save an empty, zero or negative limit', async () => {
    renderPage(status())
    await userEvent.click(await screen.findByRole('button', { name: /add budget/i }))
    const dialog = screen.getByRole('dialog')
    const save = within(dialog).getByRole('button', { name: /save budget/i })
    const limit = within(dialog).getByLabelText(/monthly limit/i)
    expect(save).toBeDisabled()
    for (const bad of ['0', '-50']) {
      await userEvent.clear(limit); await userEvent.type(limit, bad)
      expect(save).toBeDisabled()
    }
    await userEvent.clear(limit); await userEvent.type(limit, '1500.50')
    expect(save).toBeEnabled()
    expect(api.put).not.toHaveBeenCalled()
  })
})

describe('Budgets page - editing and deleting', () => {
  it('edits the limit and alert level without letting you change the category', async () => {
    renderPage(status({ budgets: [row({ monthly_limit: 5000 })] }))
    await userEvent.click(await screen.findByRole('button', { name: 'Edit Food & Dining budget' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).queryByLabelText('Category')).not.toBeInTheDocument()
    const limit = within(dialog).getByLabelText(/monthly limit/i)
    expect(limit).toHaveValue(5000)
    await userEvent.clear(limit); await userEvent.type(limit, '7500')
    await userEvent.click(within(dialog).getByRole('button', { name: /save budget/i }))
    expect(api.put).toHaveBeenCalledWith('/budgets', { category_id: 'c1', monthly_limit: 7500, alert_threshold: 80 })
  })

  it('asks before deleting, and deleting leaves transactions alone', async () => {
    renderPage(status({ budgets: [row()] }))
    await userEvent.click(await screen.findByRole('button', { name: 'Delete Food & Dining budget' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(/your transactions are not affected/i)).toBeInTheDocument()
    expect(api.delete).not.toHaveBeenCalled()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete budget' }))
    expect(api.delete).toHaveBeenCalledWith('/budgets/b1')
  })

  it('shows an error with retry when the status cannot load', async () => {
    renderPage(new Error('Server down'))
    expect(await screen.findByText("Couldn't load this")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})

describe('Dashboard budgets card', () => {
  const wrap = (props) => renderWithProviders(<BudgetsCard {...props} />)

  it('shows the most-used budgets first, at most four, with a warning badge', () => {
    const budgets = [10, 90, 50, 120, 30].map((p, i) => row({ id: `b${i}`, name: `Cat ${p}`, percent: p, spent: p * 10, monthly_limit: 1000, status: p > 100 ? 'over' : p >= 80 ? 'warning' : 'ok', remaining: 1000 - p * 10 }))
    wrap({ data: status({ budgets, summary: { over: 1, warning: 1, ok: 3 } }) })
    const bars = screen.getAllByRole('progressbar').map((b) => b.getAttribute('aria-label'))
    expect(bars).toEqual(['Cat 120 budget', 'Cat 90 budget', 'Cat 50 budget', 'Cat 30 budget'])
    expect(screen.getByText('1 over budget')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /manage/i })).toHaveAttribute('href', '/budgets')
  })

  it('invites you to create a first budget', () => {
    wrap({ data: status() })
    expect(screen.getByRole('link', { name: 'Create a budget' })).toHaveAttribute('href', '/budgets')
  })

  it('renders nothing when budgets fail to load, so the dashboard still works', () => {
    wrap({ data: null, error: 'nope' })
    expect(screen.queryByText('Budgets')).not.toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})
