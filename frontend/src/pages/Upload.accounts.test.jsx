import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, tokenStore } from '../api/client'
import { FilterProvider } from '../context/FilterContext'
import { mockSignedInApi, renderWithProviders } from '../test/utils'
import Upload from './Upload'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }
})

const BANKS = [{ key: 'sbi', bank_name: 'State Bank of India', account_type: 'bank' }, { key: 'hdfc_card', bank_name: 'HDFC Bank Credit Card', account_type: 'credit_card' }]
const acct = (o) => ({ id: 'a1', name: 'SBI Salary', account_type: 'bank', bank_name: 'State Bank of India', last4: '5555', color: '#2F7D55', ...o })
const list = (accounts) => ({ accounts, unassigned: null, totals: {} })

const previewFor = ({ upload, ...rest } = {}) => ({
  upload: {
    id: 'up1', bank_name: 'State Bank of India', account_type: 'bank', file_name: 'sbi.csv', parser_used: 'sbi:csv', parsed_count: 3, duplicate_count: 0,
    total_debits: 100, total_credits: 200, warnings: [], date_range: { start: '2025-08-01', end: '2025-08-31' }, ...upload,
  },
  new_count: 3, uncategorized_count: 0, transactions: [], suggested_account_id: null, ...rest,
})

function setup(accounts, overrides = {}) {
  mockSignedInApi(api, tokenStore, { '/accounts': list(accounts), '/statements/banks': BANKS, '/statements': [], ...overrides })
  return renderWithProviders(<FilterProvider><Upload /></FilterProvider>, { route: '/upload' })
}

async function toReview(preview) {
  fireEvent.change(document.querySelector('input[type=file]'), { target: { files: [new File(['x'.repeat(2048)], 'sbi.csv', { type: 'text/csv' })] } })
  api.post.mockResolvedValueOnce({ data: preview })
  await userEvent.click(screen.getByRole('button', { name: /analyse statement/i }))
  return screen.findByLabelText('Account')
}
const options = (select) => within(select).getAllByRole('option').map((o) => o.textContent)
const confirmCall = () => api.post.mock.calls.find(([u]) => u.endsWith('/confirm'))

beforeEach(() => {
  sessionStorage.clear()
  for (const m of [api.get, api.post, api.patch, api.put, api.delete]) m.mockReset()
})

describe('Upload review - choosing the account', () => {
  it('preselects the account Tally matched to this bank and files the statement under it', async () => {
    setup([acct({}), acct({ id: 'a9', name: 'HDFC Card', account_type: 'credit_card' })])
    const select = await toReview(previewFor({ suggested_account_id: 'a1' }))
    await waitFor(() => expect(options(select)).toContain('SBI Salary ••5555'))
    expect(select).toHaveValue('a1')
    expect(options(select)).toEqual(['Don\'t file under an account', 'SBI Salary ••5555', '+ New account…'])   // no cards for a bank statement
    expect(screen.getByText(/Matched to your account for this bank/)).toBeInTheDocument()

    api.post.mockResolvedValueOnce({ data: { id: 'up1', transaction_count: 3, duplicate_count: 0, bank_name: 'State Bank of India', account_id: 'a1' } })
    await userEvent.click(screen.getByRole('button', { name: /import 3 transactions/i }))
    expect(confirmCall()).toEqual(['/statements/up1/confirm', { include_duplicates: false, account_id: 'a1' }])
    expect(await screen.findByText(/3 transactions from State Bank of India were added to your account/)).toBeInTheDocument()
  })

  it('imports without an account when none is chosen (and sends no account at all)', async () => {
    setup([acct({})])
    const select = await toReview(previewFor())
    await waitFor(() => expect(options(select)).toContain('SBI Salary ••5555'))
    expect(select).toHaveValue('')
    expect(screen.queryByText(/Matched to your account/)).not.toBeInTheDocument()
    api.post.mockResolvedValueOnce({ data: { id: 'up1', transaction_count: 3, duplicate_count: 0, bank_name: 'State Bank of India', account_id: null } })
    await userEvent.click(screen.getByRole('button', { name: /import 3 transactions/i }))
    expect(confirmCall()[1]).toEqual({ include_duplicates: false })
  })

  it('lets you pick a different account than the suggestion', async () => {
    setup([acct({}), acct({ id: 'a2', name: 'SBI Joint', last4: null })])
    const select = await toReview(previewFor({ suggested_account_id: 'a1' }))
    await waitFor(() => expect(options(select)).toContain('SBI Joint'))
    await userEvent.selectOptions(select, 'a2')
    api.post.mockResolvedValueOnce({ data: { id: 'up1', transaction_count: 3, duplicate_count: 0, bank_name: 'x', account_id: 'a2' } })
    await userEvent.click(screen.getByRole('button', { name: /import 3 transactions/i }))
    expect(confirmCall()[1].account_id).toBe('a2')
    expect(screen.queryByText(/Matched to your account/)).not.toBeInTheDocument()
  })

  it('offers only cards for a card statement', async () => {
    setup([acct({}), acct({ id: 'a9', name: 'HDFC Card', account_type: 'credit_card', last4: null })])
    const select = await toReview(previewFor({ upload: { account_type: 'credit_card', bank_name: 'HDFC Bank Credit Card' }, suggested_account_id: 'a9' }))
    await waitFor(() => expect(options(select)).toContain('HDFC Card'))
    expect(options(select)).toEqual(['Don\'t file under an account', 'HDFC Card', '+ New account…'])
    expect(select).toHaveValue('a9')
  })

  it('creates the account right there, named after the bank, and files the statement under it', async () => {
    setup([])
    const select = await toReview(previewFor())
    api.post.mockResolvedValueOnce({ data: { id: 'new1', name: 'State Bank of India' } })
    mockSignedInApi(api, tokenStore, { '/accounts': list([acct({ id: 'new1', name: 'State Bank of India', last4: null })]), '/statements/banks': BANKS, '/statements': [] })
    await userEvent.selectOptions(select, '__new__')
    const dialog = screen.getByRole('dialog', { name: 'New account' })
    expect(within(dialog).getByLabelText('Name')).toHaveValue('State Bank of India')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.getByLabelText('Account')).toHaveValue('new1'))
    api.post.mockResolvedValueOnce({ data: { id: 'up1', transaction_count: 3, duplicate_count: 0, bank_name: 'x', account_id: 'new1' } })
    await userEvent.click(screen.getByRole('button', { name: /import 3 transactions/i }))
    expect(confirmCall()[1].account_id).toBe('new1')
  })

  it('starts the next upload with no account chosen', async () => {
    setup([acct({})])
    const select = await toReview(previewFor({ suggested_account_id: 'a1' }))
    await waitFor(() => expect(select).toHaveValue('a1'))
    api.delete.mockResolvedValue({})
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    const next = await toReview(previewFor())
    await waitFor(() => expect(options(next)).toContain('SBI Salary ••5555'))
    expect(next).toHaveValue('')
  })
})
