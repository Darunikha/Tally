import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, tokenStore } from '../../api/client'
import CategoriesRules from '../../pages/CategoriesRules'
import { FilterProvider } from '../../context/FilterContext'
import { apiError, mockSignedInApi, renderWithProviders } from '../../test/utils'
import TransactionDetail from '../TransactionDetail'
import { SuggestedRules, UncategorisedMerchants } from './LearningPanels'
import LearnRulePrompt from './LearnRulePrompt'

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }
})

beforeEach(() => {
  sessionStorage.clear()
  for (const m of [api.get, api.post, api.patch, api.put, api.delete]) m.mockReset()
})

const OFFER = { merchant: 'Swiggy', category_id: 'c-groc', category_name: 'Groceries', applies_to: 'debit', similar_count: 3 }
const RULE_OK = (recategorized) => ({ data: { rule_id: 'r1', rule_name: 'Learned: Swiggy', created: true, recategorized, category_name: 'Groceries' } })

describe('LearnRulePrompt', () => {
  const open = (offer = OFFER) => {
    const onDone = vi.fn(); const onClose = vi.fn()
    renderWithProviders(<LearnRulePrompt offer={offer} onDone={onDone} onClose={onClose} />)
    return { onDone, onClose }
  }

  it('asks the question in plain words and says what will move', () => {
    open()
    expect(screen.getByRole('dialog', { name: 'Remember this?' })).toBeInTheDocument()
    expect(screen.getByText(/Always file/)).toHaveTextContent('Always file Swiggy under Groceries?')
    expect(screen.getByText(/3 other Swiggy transactions will move too/)).toBeInTheDocument()
    expect(screen.getByText(/Anything you have set by hand stays as you left it/)).toBeInTheDocument()
  })

  it('does not promise to move anything when nothing would move', () => {
    open({ ...OFFER, similar_count: 0 })
    expect(screen.getByText(/Future statements will follow it automatically/)).toBeInTheDocument()
    expect(screen.queryByText(/will move too/)).not.toBeInTheDocument()
  })

  it('uses the singular for one transaction', () => {
    open({ ...OFFER, similar_count: 1 })
    expect(screen.getByText(/1 other Swiggy transaction will move too/)).toBeInTheDocument()
  })

  it('starts with the kind of transaction you corrected', () => {
    open({ ...OFFER, applies_to: 'credit' })
    expect(screen.getByRole('tab', { name: 'Credits' })).toHaveAttribute('aria-selected', 'true')
  })

  it('creates the rule with the chosen scope and tells you what happened', async () => {
    const { onDone, onClose } = open()
    api.post.mockResolvedValueOnce(RULE_OK(3))
    await userEvent.click(screen.getByRole('tab', { name: 'Both' }))
    await userEvent.click(screen.getByRole('button', { name: /create rule/i }))
    expect(api.post).toHaveBeenCalledWith('/rules/learn', { merchant: 'Swiggy', category_id: 'c-groc', applies_to: 'any' })
    expect(await screen.findByText('3 transactions moved to Groceries.')).toBeInTheDocument()
    expect(onDone).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('says it will apply to future transactions when none needed moving', async () => {
    open()
    api.post.mockResolvedValueOnce(RULE_OK(0))
    await userEvent.click(screen.getByRole('button', { name: /create rule/i }))
    expect(await screen.findByText('Future Swiggy transactions will go to Groceries.')).toBeInTheDocument()
  })

  it('leaves everything alone on "Not now"', async () => {
    const { onDone, onClose } = open()
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
    expect(api.post).not.toHaveBeenCalled()
    expect(onDone).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('stays open with the reason when it fails', async () => {
    const { onDone, onClose } = open()
    api.post.mockRejectedValueOnce(apiError(400, 'not_learnable', "Tally can't make a rule for that payee."))
    await userEvent.click(screen.getByRole('button', { name: /create rule/i }))
    expect(await screen.findByText("Tally can't make a rule for that payee.")).toBeInTheDocument()
    expect(onDone).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /create rule/i })).toBeEnabled()
  })
})

describe('correcting a transaction', () => {
  const CATEGORIES = [{ id: 'c-food', name: 'Food & Dining' }, { id: 'c-groc', name: 'Groceries' }]
  const TXN = {
    id: 't1', normalized_merchant: 'Swiggy', raw_description: 'SWIGGY ORDER 1', amount: 300, transaction_type: 'debit', transaction_date: '2025-08-01',
    category_id: 'c-food', category_name: 'Food & Dining', category_color: '#1BAF7A', categorization_source: 'rule', payment_method: 'UPI', notes: '',
  }
  const mount = () => {
    const onSaved = vi.fn(); const onClose = vi.fn()
    api.get.mockResolvedValue({ data: TXN })
    renderWithProviders(<TransactionDetail txn={TXN} categories={CATEGORIES} onSaved={onSaved} onClose={onClose} />)
    return { onSaved, onClose }
  }
  const changeCategory = async () => {
    await userEvent.selectOptions(screen.getByLabelText('Category'), 'c-groc')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
  }

  it('offers to remember the correction, keeping the saved change either way', async () => {
    const { onSaved, onClose } = mount()
    api.patch.mockResolvedValueOnce({ data: { ...TXN, category_id: 'c-groc', suggestion: OFFER } })
    await changeCategory()
    expect(api.patch).toHaveBeenCalledWith('/transactions/t1', { category_id: 'c-groc' })
    expect(await screen.findByRole('dialog', { name: 'Remember this?' })).toBeInTheDocument()
    expect(onSaved).toHaveBeenCalledTimes(1)       // the list already shows the change
    expect(onClose).not.toHaveBeenCalled()
  })

  it('closes for good on "Not now"', async () => {
    const { onSaved, onClose } = mount()
    api.patch.mockResolvedValueOnce({ data: { ...TXN, suggestion: OFFER } })
    await changeCategory()
    await userEvent.click(await screen.findByRole('button', { name: 'Not now' }))
    expect(api.post).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(onSaved).toHaveBeenCalledTimes(1)
  })

  it('creates the rule, refreshes the lists, and closes', async () => {
    const { onSaved, onClose } = mount()
    api.patch.mockResolvedValueOnce({ data: { ...TXN, suggestion: OFFER } })
    api.post.mockResolvedValueOnce(RULE_OK(3))
    await changeCategory()
    await userEvent.click(await screen.findByRole('button', { name: /create rule/i }))
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
    expect(api.post).toHaveBeenCalledWith('/rules/learn', { merchant: 'Swiggy', category_id: 'c-groc', applies_to: 'debit' })
    expect(onSaved).toHaveBeenCalledTimes(2)       // once for the correction, once for what the rule moved
  })

  it('just closes when there is nothing to offer', async () => {
    const { onClose } = mount()
    api.patch.mockResolvedValueOnce({ data: { ...TXN, suggestion: null } })
    await changeCategory()
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
    expect(screen.queryByRole('dialog', { name: 'Remember this?' })).not.toBeInTheDocument()
  })

  it('does not offer anything for a note-only change', async () => {
    const { onClose } = mount()
    api.patch.mockResolvedValueOnce({ data: { ...TXN, notes: 'x' } })
    await userEvent.type(screen.getByLabelText('Notes'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })
})

describe('SuggestedRules', () => {
  const S = [
    { merchant: 'Swiggy', category_id: 'c-groc', category_name: 'Groceries', category_color: '#008300', evidence: 3, applies_to: 'debit', affected: 7 },
    { merchant: 'Priya S', category_id: 'c-trans', category_name: 'Transfers', category_color: '#94A3B8', evidence: 2, applies_to: 'any', affected: 1 },
    { merchant: 'Bank Interest', category_id: 'c-inc', category_name: 'Income', category_color: '#2F7D55', evidence: 2, applies_to: 'credit', affected: 0 },
  ]
  const mount = (suggestions = S, onChanged = vi.fn()) => {
    mockSignedInApi(api, tokenStore, { '/categories/suggestions': suggestions })
    renderWithProviders(<FilterProvider><SuggestedRules version={0} onChanged={onChanged} /></FilterProvider>)
    return onChanged
  }
  const list = () => screen.findByRole('list', { name: 'Suggested rules' })

  it('explains each suggestion with the evidence', async () => {
    mount()
    const rows = within(await list()).getAllByRole('listitem')
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent('Swiggy→Groceries')
    expect(rows[0]).toHaveTextContent('You moved it there 3 times · would also move 7 other transactions · payments only')
    expect(rows[1]).toHaveTextContent('would also move 1 other transaction')
    expect(rows[1]).not.toHaveTextContent('only')                     // a both-ways rule has no scope note
    expect(rows[2]).toHaveTextContent('money received only')
    expect(rows[2]).not.toHaveTextContent('would also move')          // nothing else to move
  })

  it('shows nothing at all when there are no suggestions, or they cannot be loaded', async () => {
    mount([])
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/categories/suggestions', expect.anything()))
    expect(screen.queryByText('Tally noticed a pattern')).not.toBeInTheDocument()
  })

  it('creates the rule you accept, in the scope it was learned for', async () => {
    const onChanged = mount()
    api.post.mockResolvedValueOnce(RULE_OK(7))
    await userEvent.click(await screen.findByRole('button', { name: 'Create a rule for Swiggy' }))
    expect(api.post).toHaveBeenCalledWith('/rules/learn', { merchant: 'Swiggy', category_id: 'c-groc', applies_to: 'debit' })
    expect(await screen.findByText('7 transactions moved to Groceries.')).toBeInTheDocument()
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it('remembers a "not now" without creating anything', async () => {
    mount()
    api.post.mockResolvedValueOnce({ data: {} })
    await userEvent.click(await screen.findByRole('button', { name: 'Not now for Priya S' }))
    expect(api.post).toHaveBeenCalledWith('/categories/suggestions/dismiss', { merchant: 'Priya S', category_id: 'c-trans' })
    expect(api.post).not.toHaveBeenCalledWith('/rules/learn', expect.anything())
  })

  it('shows why a rule could not be made', async () => {
    mount()
    api.post.mockRejectedValueOnce(apiError(404, 'not_found', 'Category not found'))
    await userEvent.click(await screen.findByRole('button', { name: 'Create a rule for Swiggy' }))
    expect(await screen.findByText('Category not found')).toBeInTheDocument()
  })
})

describe('UncategorisedMerchants', () => {
  const CATS = [{ id: 'c-food', name: 'Food & Dining' }, { id: 'c-shop', name: 'Shopping' }, { id: 'c-other', name: 'Other' }]
  const ROWS = [
    { merchant: 'Zxqv Qwerty', count: 3, total: 600, sample: 'ZXQV QWERTY 1', applies_to: 'debit' },
    { merchant: 'Plugh Xyzzy', count: 1, total: 50, sample: 'PLUGH XYZZY 1', applies_to: 'debit' },
  ]
  const mount = (rows = ROWS, onChanged = vi.fn()) => {
    mockSignedInApi(api, tokenStore, { '/categories/uncategorised': rows })
    renderWithProviders(<FilterProvider><UncategorisedMerchants categories={CATS} version={0} onChanged={onChanged} /></FilterProvider>)
    return onChanged
  }
  const rows = async () => within(await screen.findByRole('list', { name: 'Merchants that need a category' })).getAllByRole('listitem')

  it('lists each merchant with what is at stake', async () => {
    mount()
    const [first, second] = await rows()
    expect(first).toHaveTextContent('Zxqv Qwerty')
    expect(first).toHaveTextContent('3 transactions · ₹600')
    expect(first).toHaveTextContent('ZXQV QWERTY 1')
    expect(second).toHaveTextContent('1 transaction · ₹50')
  })

  it('will not apply until a category is chosen, and never offers "Other"', async () => {
    mount()
    const [first] = await rows()
    const apply = within(first).getByRole('button', { name: 'Apply to all Zxqv Qwerty transactions' })
    expect(apply).toBeDisabled()
    const select = within(first).getByLabelText('Category for Zxqv Qwerty')
    expect([...select.options].map((o) => o.textContent)).toEqual(['Choose a category…', 'Food & Dining', 'Shopping'])
    await userEvent.selectOptions(select, 'c-shop')
    expect(apply).toBeEnabled()
  })

  it('sorts every transaction from the merchant with one choice and remembers it', async () => {
    const onChanged = mount()
    api.post.mockResolvedValueOnce({ data: { recategorized: 3, created: true } })
    const [first] = await rows()
    await userEvent.selectOptions(within(first).getByLabelText('Category for Zxqv Qwerty'), 'c-shop')
    await userEvent.click(within(first).getByRole('button', { name: /apply to all/i }))
    expect(api.post).toHaveBeenCalledWith('/rules/learn', { merchant: 'Zxqv Qwerty', category_id: 'c-shop', applies_to: 'debit' })
    expect(await screen.findByText('3 transactions moved to Shopping.')).toBeInTheDocument()
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it('keeps each merchant\'s choice separate', async () => {
    mount()
    const [first, second] = await rows()
    await userEvent.selectOptions(within(first).getByLabelText('Category for Zxqv Qwerty'), 'c-food')
    expect(within(second).getByLabelText('Category for Plugh Xyzzy')).toHaveValue('')
    expect(within(second).getByRole('button', { name: /apply to all/i })).toBeDisabled()
  })

  it('is silent when everything has a category', async () => {
    mount([])
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/categories/uncategorised', expect.anything()))
    expect(screen.queryByText('Needs a category')).not.toBeInTheDocument()
  })
})

describe('Categories & Rules page', () => {
  const page = (tab) => {
    mockSignedInApi(api, tokenStore, {
      '/categories': [{ id: 'c1', name: 'Shopping', color: '#EB6834', is_default: true, transaction_count: 3, rule_count: 1, description: '' }],
      '/rules': [], '/categories/suggestions': [{ merchant: 'Swiggy', category_id: 'c1', category_name: 'Shopping', category_color: '#EB6834', evidence: 2, applies_to: 'debit', affected: 1 }],
      '/categories/uncategorised': [{ merchant: 'Zxqv', count: 2, total: 100, sample: 'ZXQV 1', applies_to: 'debit' }],
    })
    renderWithProviders(<FilterProvider><CategoriesRules /></FilterProvider>, { route: '/categories' })
    return tab
  }

  it('puts what Tally learned above the categories', async () => {
    page()
    expect(await screen.findByText('Tally noticed a pattern')).toBeInTheDocument()
    expect(screen.getByText('Needs a category')).toBeInTheDocument()
    expect(screen.getByText('Shopping', { selector: 'p' })).toBeInTheDocument()
  })

  it('keeps them off the rules tab', async () => {
    page()
    await screen.findByText('Tally noticed a pattern')
    await userEvent.click(screen.getByRole('tab', { name: /Rules/ }))
    expect(screen.queryByText('Tally noticed a pattern')).not.toBeInTheDocument()
    expect(screen.queryByText('Needs a category')).not.toBeInTheDocument()
  })
})

describe('accessibility of the merchant list', () => {
  it('gives every category picker a valid id (no spaces) tied to its label', async () => {
    mockSignedInApi(api, tokenStore, { '/categories/uncategorised': [
      { merchant: 'Zxqv Qwerty', count: 1, total: 1, sample: 's', applies_to: 'debit' }, { merchant: 'Two  Spaces & Co.', count: 1, total: 1, sample: 's', applies_to: 'debit' },
    ] })
    renderWithProviders(<FilterProvider><UncategorisedMerchants categories={[{ id: 'c', name: 'Shopping' }]} version={0} /></FilterProvider>)
    const selects = (await screen.findAllByRole('combobox'))
    expect(selects).toHaveLength(2)
    for (const s of selects) expect(s.id).toMatch(/^[A-Za-z0-9_-]+$/)
    expect(new Set(selects.map((s) => s.id)).size).toBe(2)
    expect(screen.getByLabelText('Category for Two Spaces & Co.')).toBe(selects[1])
  })
})
