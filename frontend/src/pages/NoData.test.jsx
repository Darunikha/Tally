import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, tokenStore } from '../api/client'
import { FilterProvider } from '../context/FilterContext'
import { mockSignedInApi, renderWithProviders } from '../test/utils'
import Analytics from './Analytics'
import Anomalies from './Anomalies'
import Dashboard from './Dashboard'
import Transactions from './Transactions'
import UpiAnalysis from './UpiAnalysis'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }
})

const STATEMENT = { id: 's1', bank_name: 'HDFC Bank', file_name: 'hdfc.csv', account_id: null, account_type: 'bank' }
const DASH = {
  period: { start: '2025-10-01', end: '2025-10-31' }, previous_period: null,
  totals: { total_income: 1000, total_expenses: 500, net_balance: 500, transaction_count: 5, debit_count: 3, credit_count: 2, upi_spending: 100, upi_transaction_count: 1, avg_daily_spending: 16, days: 31, savings_rate: 50 },
  changes: {}, category_breakdown: [], daily_trend: [], trend_granularity: 'day', monthly: [], top_merchants: [], recent_transactions: [], insights: [], excluded_payments: { count: 0 },
}
const onboarding = (o = {}) => ({
  steps: [
    { key: 'statement', title: 'Add your first statement', done: true, href: '/upload', description: 'd1' },
    { key: 'account', title: 'File it under an account', done: false, href: '/accounts', description: 'd2' },
    { key: 'review', title: 'Review uncategorised transactions', done: false, href: '/transactions?needs_review=true', description: 'd3' },
    { key: 'budget', title: 'Set a budget', done: false, href: '/budgets', description: 'd4' },
  ], completed: 1, total: 4, welcome_seen: true, checklist_dismissed: false, show_checklist: true, ...o,
})

beforeEach(() => {
  sessionStorage.clear()
  for (const m of [api.get, api.post, api.patch, api.put, api.delete]) m.mockReset()
})

// the page renders normally for an instant before the filter context is ready; wait that out before judging it
const settled = () => act(async () => { await new Promise((r) => setTimeout(r, 80)) })
const prompt = () => screen.findByRole('heading', { name: 'Add your first statement' }, { timeout: 4000 })

const render = (Page, overrides = {}) => {
  mockSignedInApi(api, tokenStore, overrides)
  return renderWithProviders(<FilterProvider><Page /></FilterProvider>, { route: '/' })
}
// a piece of each page's own furniture: present on a normal page, absent behind the "add a statement" prompt
// (the last item is what the page needs from the API to render normally once there is data)
const PAGES = [
  ['Dashboard', Dashboard, () => screen.queryByText('Total Income'), { '/analytics/dashboard': DASH }],
  ['Transactions', Transactions, () => screen.queryByPlaceholderText(/Search merchant/), {}],
  ['Analytics', Analytics, () => screen.queryByText(/Detailed spending analysis/), {}],
  ['UPI Analysis', UpiAnalysis, () => screen.queryByText(/UPI merchant intelligence/), {}],
  ['Anomalies', Anomalies, () => screen.queryByText(/Unusual activity worth a look/), {}],
]

describe.each(PAGES)('%s with no statements yet', (name, Page, furniture, pageData) => {
  it('leads with one clear next step', async () => {
    render(Page, { '/onboarding': onboarding({ show_checklist: false }) })
    expect(await prompt()).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /upload a statement/i })).toHaveAttribute('href', '/upload')
    expect(screen.getByRole('button', { name: /try with demo data/i })).toBeInTheDocument()
    expect(furniture()).not.toBeInTheDocument() // none of the page's normal furniture
  })

  it('does not say "all clear" or "nothing found" to someone with no data', async () => {
    render(Page, { '/onboarding': onboarding({ show_checklist: false }) })
    await prompt()
    expect(screen.queryByText(/nothing unusual found|no transactions found|nothing to analyse/i)).not.toBeInTheDocument()
  })

  it('goes away once there is a statement', async () => {
    render(Page, { '/analytics/statements-filter': [STATEMENT], '/onboarding': onboarding({ show_checklist: false }), '/budgets/status': new Error('none'), ...pageData })
    await settled()
    await waitFor(() => expect(furniture()).toBeInTheDocument()) // the real page is there...
    expect(screen.queryByRole('heading', { name: 'Add your first statement' })).not.toBeInTheDocument() // ...without the prompt
    expect(screen.queryByRole('button', { name: /try with demo data/i })).not.toBeInTheDocument()
  })
})

describe('Dashboard onboarding', () => {
  const withData = (o = {}) => ({
    '/analytics/statements-filter': [STATEMENT], '/analytics/dashboard': DASH, '/budgets/status': new Error('none'), '/categories': [], ...o,
  })

  it('welcomes a brand new user once, and remembers that it did', async () => {
    let state = onboarding({ welcome_seen: false })
    render(Dashboard, { '/onboarding': () => state })
    api.patch.mockImplementation((url, body) => { state = { ...state, ...body }; return Promise.resolve({ data: state }) })
    const tour = await screen.findByRole('dialog')
    expect(tour).toHaveAccessibleName('Welcome to Tally, Dee')
    await userEvent.click(within(tour).getByRole('button', { name: 'Skip for now' }))
    expect(api.patch).toHaveBeenCalledWith('/onboarding', { welcome_seen: true })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('does not welcome someone who has already seen it', async () => {
    render(Dashboard, { '/onboarding': onboarding({ welcome_seen: true }) })
    await prompt()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows the checklist once there is data, with the next step to take', async () => {
    render(Dashboard, withData({ '/onboarding': onboarding() }))
    expect(await screen.findByText('Get set up')).toBeInTheDocument()
    expect(screen.getByText('1 of 4 done')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'File it under an account: go' })).toHaveAttribute('href', '/accounts')
    expect(screen.getByRole('link', { name: 'Set a budget: go' })).toHaveAttribute('href', '/budgets')
  })

  it('hides the checklist for good when asked', async () => {
    let state = onboarding()
    render(Dashboard, withData({ '/onboarding': () => state }))
    api.patch.mockImplementation((url, body) => { state = onboarding({ ...body, show_checklist: false }); return Promise.resolve({ data: state }) })
    await userEvent.click(await screen.findByRole('button', { name: 'Hide the getting started checklist' }))
    expect(api.patch).toHaveBeenCalledWith('/onboarding', { checklist_dismissed: true })
    await waitFor(() => expect(screen.queryByText('Get set up')).not.toBeInTheDocument())
  })

  it('stays out of the way when it is finished or dismissed', async () => {
    render(Dashboard, withData({ '/onboarding': onboarding({ show_checklist: false, completed: 4 }) }))
    await screen.findByText('Total Income')
    expect(screen.queryByText('Get set up')).not.toBeInTheDocument()
  })

  it('does not stack the checklist on the first-statement prompt', async () => {
    render(Dashboard, { '/onboarding': onboarding({ show_checklist: true, welcome_seen: true }) })
    await prompt()
    expect(screen.queryByText('Get set up')).not.toBeInTheDocument()
  })

  it('still shows the dashboard if the onboarding service is unavailable', async () => {
    render(Dashboard, withData({ '/onboarding': new Error('down') }))
    expect(await screen.findByText('Total Income')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
