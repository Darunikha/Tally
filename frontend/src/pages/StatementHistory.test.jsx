import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, tokenStore } from '../api/client'
import { FilterProvider } from '../context/FilterContext'
import { mockSignedInApi, renderWithProviders } from '../test/utils'
import StatementHistory from './StatementHistory'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }
})

const stmt = (o) => ({
  id: 's1', file_name: 'hdfc.csv', file_type: 'csv', file_size: 2048, bank_name: 'HDFC Bank', account_type: 'bank', account_id: null, parser_used: 'hdfc:csv',
  upload_date: '2025-11-01T10:00:00Z', date_range: { start: '2025-08-01', end: '2025-08-31' }, transaction_count: 30, duplicate_count: 0,
  total_debits: 1000, total_credits: 2000, processing_status: 'completed', ...o,
})
const ACCOUNTS = [
  { id: 'a1', name: 'HDFC Savings', account_type: 'bank', bank_name: 'HDFC Bank', last4: '4321', color: '#2F7D55' },
  { id: 'a2', name: 'HDFC Card', account_type: 'credit_card', bank_name: 'HDFC Bank Credit Card', last4: null, color: '#2A78D6' },
]

function renderPage(statements) {
  mockSignedInApi(api, tokenStore, { '/accounts': { accounts: ACCOUNTS, unassigned: null, totals: {} }, '/statements': statements })
  api.put.mockResolvedValue({ data: { account_id: 'a1', moved_transactions: 30 } })
  return renderWithProviders(<FilterProvider><StatementHistory /></FilterProvider>, { route: '/statements' })
}
const rowOf = async (name) => (await screen.findByText(name)).closest('tr')
const options = (select) => within(select).getAllByRole('option').map((o) => o.textContent)

beforeEach(() => {
  sessionStorage.clear()
  for (const m of [api.get, api.post, api.patch, api.put, api.delete]) m.mockReset()
})

describe('Statement history - account column', () => {
  it('shows which account each statement is filed under', async () => {
    renderPage([stmt({ account_id: 'a1' }), stmt({ id: 's2', file_name: 'old.csv' })])
    const filed = within(await rowOf('hdfc.csv')).getByRole('combobox')
    await waitFor(() => expect(options(filed)).toContain('HDFC Savings ••4321'))
    expect(filed).toHaveValue('a1')
    expect(within(await rowOf('old.csv')).getByRole('combobox')).toHaveValue('')
  })

  it('only offers accounts of the statement\'s kind', async () => {
    renderPage([stmt({}), stmt({ id: 's3', file_name: 'card.csv', account_type: 'credit_card', bank_name: 'HDFC Bank Credit Card' })])
    const bank = within(await rowOf('hdfc.csv')).getByRole('combobox')
    const card = within(await rowOf('card.csv')).getByRole('combobox')
    await waitFor(() => expect(options(bank).length).toBeGreaterThan(2))
    expect(options(bank)).toEqual(['Not filed', 'HDFC Savings ••4321', '+ New account…'])
    expect(options(card)).toEqual(['Not filed', 'HDFC Card', '+ New account…'])
  })

  it('moves a statement to another account', async () => {
    renderPage([stmt({})])
    const select = within(await rowOf('hdfc.csv')).getByRole('combobox')
    await waitFor(() => expect(options(select).length).toBeGreaterThan(2))
    await userEvent.selectOptions(select, 'a1')
    expect(api.put).toHaveBeenCalledWith('/statements/s1/account', { account_id: 'a1' })
    expect(await screen.findByText('Statement moved')).toBeInTheDocument()
  })

  it('can take a statement out of its account', async () => {
    renderPage([stmt({ account_id: 'a1' })])
    const select = within(await rowOf('hdfc.csv')).getByRole('combobox')
    await waitFor(() => expect(select).toHaveValue('a1'))
    await userEvent.selectOptions(select, '')
    expect(api.put).toHaveBeenCalledWith('/statements/s1/account', { account_id: null })
    expect(await screen.findByText('Statement is no longer filed under an account')).toBeInTheDocument()
  })

  it('shows the reason when a move is refused', async () => {
    renderPage([stmt({})])
    api.put.mockRejectedValueOnce(Object.assign(new Error('x'), { response: { status: 400, data: { error: { code: 'account_type_mismatch', message: 'Choose a bank account, not a card.' } } } }))
    const select = within(await rowOf('hdfc.csv')).getByRole('combobox')
    await waitFor(() => expect(options(select).length).toBeGreaterThan(2))
    await userEvent.selectOptions(select, 'a1')
    expect(await screen.findByText('Choose a bank account, not a card.')).toBeInTheDocument()
  })

  it('has no account choice for failed imports', async () => {
    renderPage([stmt({ id: 's9', file_name: 'broken.csv', processing_status: 'failed', error: 'Could not parse' })])
    expect(within(await rowOf('broken.csv')).queryByRole('combobox')).not.toBeInTheDocument()
  })
})
