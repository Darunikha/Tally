import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, tokenStore } from '../api/client'
import { FilterProvider } from '../context/FilterContext'
import { mockSignedInApi, renderWithProviders } from '../test/utils'
import Accounts from './Accounts'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }
})

const month = { year: 2025, month: 10, label: 'October 2025', money_in: 86275, money_out: 102509 }
const savings = {
  id: 'a1', name: 'HDFC Savings', account_type: 'bank', bank_name: 'HDFC Bank', last4: '4321', color: '#2F7D55', statement_count: 3,
  transaction_count: 133, date_range: { start: '2025-08-01', end: '2025-10-31' }, balance: { amount: 125500.5, as_of: '2025-10-31' }, latest_month: month,
}
const card = {
  id: 'a2', name: 'HDFC Card', account_type: 'credit_card', bank_name: 'HDFC Bank Credit Card', last4: null, color: '#2A78D6', statement_count: 1,
  transaction_count: 34, date_range: { start: '2025-10-01', end: '2025-10-28' }, balance: null,
  latest_month: { ...month, money_in: 41299, money_out: 35228.22 },
}
const empty = { id: 'a3', name: 'SBI Salary', account_type: 'bank', bank_name: null, last4: null, color: '#EB6834', statement_count: 0, transaction_count: 0, date_range: { start: null, end: null }, balance: null, latest_month: null }
const LIST = {
  accounts: [savings, card, empty], unassigned: null,
  totals: { bank_balance: 125500.5, bank_accounts_with_balance: 1, bank_account_count: 2, card_count: 1 },
}

function renderPage(accounts = LIST, extra = {}) {
  mockSignedInApi(api, tokenStore, { '/accounts': accounts, ...extra })
  api.post.mockResolvedValue({ data: {} })
  api.patch.mockResolvedValue({ data: {} })
  api.delete.mockResolvedValue({ data: {} })
  return renderWithProviders(<FilterProvider><Accounts /></FilterProvider>, { route: '/accounts', extraRoutes: { '/': <p>Dashboard page</p> } })
}

const card_ = async (name) => (await screen.findByRole('heading', { name: new RegExp(name) })).closest('section')

beforeEach(() => {
  sessionStorage.clear()
  for (const m of [api.get, api.post, api.patch, api.put, api.delete]) m.mockReset()
})

describe('Accounts page - overview', () => {
  it('shows what you hold across accounts', async () => {
    renderPage()
    expect(await screen.findByText('In bank accounts')).toBeInTheDocument()
    expect(screen.getByText('₹1,25,501')).toBeInTheDocument()                    // Indian grouping, rounded
    expect(screen.getByText('Bank accounts').closest('section')).toHaveTextContent('2')
    expect(screen.getByText('Credit cards').closest('section')).toHaveTextContent('1')
  })

  it('shows a bank account with its balance, date and the latest month', async () => {
    renderPage()
    const s = await card_('HDFC Savings')
    expect(s).toHaveTextContent('Bank account')
    expect(within(s).getByLabelText('ending 4321')).toHaveTextContent('••4321')
    expect(s).toHaveTextContent('₹1,25,500.50')
    expect(s).toHaveTextContent('balance as of 31 Oct 2025')
    expect(s).toHaveTextContent('Money in₹86,275')
    expect(s).toHaveTextContent('Money out₹1,02,509')
    expect(s).toHaveTextContent('October 2025 · 3 statements · 133 transactions')
    expect(s).toHaveTextContent('1 Aug 2025 – 31 Oct 2025')
  })

  it('shows a credit card by what was spent, with no balance and no money-out tile', async () => {
    renderPage()
    const c = await card_('HDFC Card')
    expect(c).toHaveTextContent('Credit card')
    expect(c).toHaveTextContent('₹35,228')
    expect(c).toHaveTextContent('spent in October 2025')
    expect(c).toHaveTextContent('Payments & refunds₹41,299')
    expect(c).not.toHaveTextContent('Money out')
    expect(c).not.toHaveTextContent('balance as of')
  })

  it('invites you to file a statement under an account that has none yet', async () => {
    renderPage()
    const e = await card_('SBI Salary')
    expect(e).toHaveTextContent('No statements yet')
    expect(within(e).getByRole('button', { name: 'Analyse' })).toBeDisabled()
  })

  it('says so when statements do not include a balance', async () => {
    renderPage({ ...LIST, accounts: [{ ...savings, balance: null }] })
    expect(await screen.findByText(/don't include a balance/)).toBeInTheDocument()
  })

  it('links to the account\'s transactions and opens it on the dashboard', async () => {
    renderPage()
    const s = await card_('HDFC Savings')
    expect(within(s).getByRole('link', { name: 'Transactions in HDFC Savings' })).toHaveAttribute('href', '/transactions?account_id=a1')
    await userEvent.click(within(s).getByRole('button', { name: 'Analyse' }))
    expect(await screen.findByText('Dashboard page')).toBeInTheDocument()
  })

  it('guides you when there are no accounts at all', async () => {
    renderPage({ accounts: [], unassigned: null, totals: { bank_balance: 0, bank_accounts_with_balance: 0, bank_account_count: 0, card_count: 0 } })
    expect(await screen.findByText('No accounts yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /upload a statement/i })).toHaveAttribute('href', '/upload')
  })

  it('shows an error with retry', async () => {
    renderPage(new Error('Server down'))
    expect(await screen.findByText("Couldn't load this")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})

describe('Accounts page - unassigned statements', () => {
  const WITH_UNASSIGNED = { ...LIST, unassigned: { statement_count: 2, transaction_count: 1500 } }

  it('offers to set up accounts automatically', async () => {
    renderPage(WITH_UNASSIGNED)
    expect(await screen.findByText(/2 statements/)).toHaveTextContent('2 statements')
    expect(screen.getByText(/1,500 transactions\) aren't filed under an account yet/)).toBeInTheDocument()
    api.post.mockResolvedValueOnce({ data: { created_accounts: 2, assigned_statements: 2 } })
    await userEvent.click(screen.getByRole('button', { name: /set up automatically/i }))
    expect(api.post).toHaveBeenCalledWith('/accounts/auto-setup')
    expect(await screen.findByText('2 statements filed, 2 accounts created')).toBeInTheDocument()
  })

  it('stays quiet when everything is filed', async () => {
    renderPage()
    await screen.findByText('In bank accounts')
    expect(screen.queryByRole('button', { name: /set up automatically/i })).not.toBeInTheDocument()
  })
})

describe('Accounts page - add, edit, delete', () => {
  it('creates an account (last 4 digits only, digits only)', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /add account/i }))
    const dialog = screen.getByRole('dialog')
    const save = within(dialog).getByRole('button', { name: 'Save' })
    expect(save).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Joint account')
    await userEvent.type(within(dialog).getByLabelText(/last 4 digits/i), '12ab3')
    expect(within(dialog).getByLabelText(/last 4 digits/i)).toHaveValue('123')   // letters are dropped
    expect(save).toBeDisabled()                                                      // three digits is not enough
    await userEvent.type(within(dialog).getByLabelText(/last 4 digits/i), '4')
    expect(save).toBeEnabled()
    await userEvent.selectOptions(within(dialog).getByLabelText('Type'), 'credit_card')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Colour #6250D6' }))
    await userEvent.click(save)
    expect(api.post).toHaveBeenCalledWith('/accounts', { name: 'Joint account', account_type: 'credit_card', bank_name: undefined, last4: '1234', color: '#6250D6' })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('never invites a full account number', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /add account/i }))
    expect(screen.getByText(/never enter a full account or card number/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/last 4 digits/i)).toHaveAttribute('maxlength', '4')
  })

  it('edits name and last digits but not the type', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Edit HDFC Savings' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByLabelText('Type')).toBeDisabled()
    const name = within(dialog).getByLabelText('Name')
    await userEvent.clear(name); await userEvent.type(name, 'HDFC Salary')
    await userEvent.clear(within(dialog).getByLabelText(/last 4 digits/i))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    expect(api.patch).toHaveBeenCalledWith('/accounts/a1', { name: 'HDFC Salary', last4: '', color: '#2F7D55' })  // colour kept as it was
  })

  it('shows the server reason when a name is already taken', async () => {
    renderPage()
    api.post.mockRejectedValueOnce(Object.assign(new Error('x'), { response: { status: 409, data: { error: { code: 'duplicate', message: "You already have an account called 'HDFC Savings'." } } } }))
    await userEvent.click(await screen.findByRole('button', { name: /add account/i }))
    await userEvent.type(screen.getByLabelText('Name'), 'HDFC Savings')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText(/You already have an account called/)).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()                          // stays open so you can fix it
  })

  it('explains that deleting keeps the statements', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Delete HDFC Savings' }))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('Its 3 statements and 133 transactions are kept and become unassigned.')
    expect(api.delete).not.toHaveBeenCalled()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete account' }))
    expect(api.delete).toHaveBeenCalledWith('/accounts/a1')
    expect(await screen.findByText('Account deleted. Its statements are kept.')).toBeInTheDocument()
  })
})
