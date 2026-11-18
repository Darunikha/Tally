import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, tokenStore } from '../api/client'
import { FilterProvider, useFilters } from '../context/FilterContext'
import { mockSignedInApi, renderWithProviders } from '../test/utils'
import PeriodPicker from './layout/PeriodPicker'
import AccountSelect from './AccountSelect'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }
})

const acct = (o) => ({ id: 'a1', name: 'HDFC Savings', account_type: 'bank', bank_name: 'HDFC Bank', last4: '4321', color: '#2F7D55', statement_count: 1, transaction_count: 5, ...o })
const ACCOUNTS = [acct({}), acct({ id: 'a2', name: 'SBI Salary', last4: null }), acct({ id: 'a3', name: 'HDFC Card', account_type: 'credit_card', last4: '9988' })]
const list = (accounts = ACCOUNTS) => ({ accounts, unassigned: null, totals: {} })

beforeEach(() => {
  sessionStorage.clear()
  for (const m of [api.get, api.post, api.patch, api.put, api.delete]) m.mockReset()
})

function Harness({ accountType = 'bank', bankName = 'HDFC Bank', initial = '' }) {
  const [value, setValue] = useState(initial)
  return (
    <>
      <label htmlFor="acc">Account</label>
      <AccountSelect id="acc" value={value} onChange={setValue} accountType={accountType} bankName={bankName} />
      <output data-testid="chosen">{value}</output>
    </>
  )
}

const mount = (ui, overrides) => {
  mockSignedInApi(api, tokenStore, { '/accounts': list(), ...overrides })
  return renderWithProviders(<FilterProvider>{ui}</FilterProvider>)
}
const optionsOf = (select) => within(select).getAllByRole('option').map((o) => o.textContent)

describe('AccountSelect', () => {
  it('offers only accounts of the statement\'s kind, with their last digits', async () => {
    mount(<Harness />)
    const select = await screen.findByLabelText('Account')
    await waitFor(() => expect(optionsOf(select).length).toBeGreaterThan(2))
    expect(optionsOf(select)).toEqual(['No account', 'HDFC Savings ••4321', 'SBI Salary', '+ New account…'])
  })

  it('offers cards for a card statement', async () => {
    mount(<Harness accountType="credit_card" />)
    const select = await screen.findByLabelText('Account')
    await waitFor(() => expect(optionsOf(select).length).toBeGreaterThan(2))
    expect(optionsOf(select)).toEqual(['No account', 'HDFC Card ••9988', '+ New account…'])
  })

  it('selects an account and can go back to none', async () => {
    mount(<Harness />)
    const select = await screen.findByLabelText('Account')
    await waitFor(() => expect(optionsOf(select).length).toBeGreaterThan(2))
    await userEvent.selectOptions(select, 'a2')
    expect(screen.getByTestId('chosen')).toHaveTextContent('a2')
    await userEvent.selectOptions(select, '')
    expect(screen.getByTestId('chosen')).toBeEmptyDOMElement()
  })

  it('creates a new account in place, named after the bank with the type fixed, and selects it', async () => {
    mount(<Harness bankName="State Bank of India" />)
    const select = await screen.findByLabelText('Account')
    await waitFor(() => expect(optionsOf(select).length).toBeGreaterThan(2))
    api.post.mockResolvedValueOnce({ data: { id: 'new1', name: 'State Bank of India' } })
    await userEvent.selectOptions(select, '__new__')
    const dialog = screen.getByRole('dialog', { name: 'New account' })
    expect(within(dialog).getByLabelText('Name')).toHaveValue('State Bank of India')
    expect(within(dialog).getByLabelText('Type')).toBeDisabled()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    expect(api.post).toHaveBeenCalledWith('/accounts', { name: 'State Bank of India', account_type: 'bank', bank_name: 'State Bank of India', last4: undefined, color: undefined })
    await waitFor(() => expect(screen.getByTestId('chosen')).toHaveTextContent('new1'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('keeps the current choice when the new-account form is cancelled', async () => {
    mount(<Harness initial="a1" />)
    const select = await screen.findByLabelText('Account')
    await waitFor(() => expect(optionsOf(select).length).toBeGreaterThan(2))
    await userEvent.selectOptions(select, '__new__')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))
    expect(screen.getByTestId('chosen')).toHaveTextContent('a1')
  })
})

// ------------------------------------------------------------------ the global account filter
function Probe() {
  const { params, dataChanged } = useFilters()
  return <><output data-testid="params">{JSON.stringify(params)}</output><button onClick={dataChanged}>refresh</button></>
}
const STATEMENTS = [
  { id: 's1', bank_name: 'HDFC Bank', file_name: 'hdfc.csv', account_id: 'a1', account_type: 'bank' },
  { id: 's2', bank_name: 'SBI', file_name: 'sbi.csv', account_id: 'a2', account_type: 'bank' },
  { id: 's3', bank_name: 'ICICI', file_name: 'old.csv', account_id: null, account_type: 'bank' },
]
const paramsNow = () => JSON.parse(screen.getByTestId('params').textContent)

describe('account filter in the period picker', () => {
  const setup = (accounts = ACCOUNTS) => {
    mount(<><PeriodPicker /><Probe /></>, { '/accounts': list(accounts), '/analytics/statements-filter': STATEMENTS })
    return screen.findByRole('button', { name: /all time|202\d/i })
  }
  const openPicker = async () => {
    await waitFor(() => expect(screen.getByTestId('params').textContent).not.toBe(''))
    await userEvent.click(screen.getAllByRole('button')[0])
    return screen.getByRole('dialog', { name: 'Choose period' })
  }

  it('has no account choice until you have an account', async () => {
    mount(<><PeriodPicker /><Probe /></>, { '/accounts': list([]) })
    await waitFor(() => expect(screen.getByTestId('params')).toBeInTheDocument())
    await userEvent.click(screen.getAllByRole('button')[0])
    expect(screen.queryByLabelText(/^Account/)).not.toBeInTheDocument()
  })

  it('filters every page by the chosen account', async () => {
    await setup()
    const dialog = await openPicker()
    expect(paramsNow().account_id).toBeUndefined()
    const select = within(dialog).getByLabelText(/Account/)
    expect(optionsOf(select)).toEqual(['All accounts', 'HDFC Savings ••4321', 'SBI Salary', 'HDFC Card ••9988', 'Not filed under an account'])
    await userEvent.selectOptions(select, 'a1')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Apply' }))
    expect(paramsNow().account_id).toBe('a1')
  })

  it('narrows the statement choices to the account, and picking an account resets the statement', async () => {
    await setup()
    const dialog = await openPicker()
    const statement = within(dialog).getByLabelText(/Statement/)
    expect(optionsOf(statement)).toHaveLength(4) // all three plus "All statements"
    await userEvent.selectOptions(statement, 's2')
    await userEvent.selectOptions(within(dialog).getByLabelText(/Account/), 'a1')
    expect(statement).toHaveValue('')             // s2 isn't in a1, so the old choice is dropped
    expect(optionsOf(statement)).toEqual(['All statements', 'HDFC Bank · hdfc.csv'])
    await userEvent.selectOptions(within(dialog).getByLabelText(/Account/), 'none')
    expect(optionsOf(statement)).toEqual(['All statements', 'ICICI · old.csv'])
  })

  it('can show only statements not filed under an account', async () => {
    await setup()
    const dialog = await openPicker()
    await userEvent.selectOptions(within(dialog).getByLabelText(/Account/), 'none')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Apply' }))
    expect(paramsNow().account_id).toBe('none')
  })

  it('names the account on the picker button', async () => {
    await setup()
    const dialog = await openPicker()
    await userEvent.selectOptions(within(dialog).getByLabelText(/Account/), 'a2')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Apply' }))
    await waitFor(() => expect(screen.getAllByRole('button')[0]).toHaveTextContent('SBI Salary'))
  })

  it('drops the filter if that account is deleted', async () => {
    await setup()
    const dialog = await openPicker()
    await userEvent.selectOptions(within(dialog).getByLabelText(/Account/), 'a1')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Apply' }))
    expect(paramsNow().account_id).toBe('a1')
    mockSignedInApi(api, tokenStore, { '/accounts': list([ACCOUNTS[1]]), '/analytics/statements-filter': STATEMENTS })
    await userEvent.click(screen.getByRole('button', { name: 'refresh' }))
    await waitFor(() => expect(paramsNow().account_id).toBeUndefined())
  })
})
