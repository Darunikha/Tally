import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { FilterProvider } from '../context/FilterContext'
import { apiError, renderWithProviders } from '../test/utils'
import Upload from './Upload'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }
})

const BANKS = [
  { key: 'hdfc', bank_name: 'HDFC Bank', account_type: 'bank' }, { key: 'sbi', bank_name: 'State Bank of India', account_type: 'bank' },
  { key: 'hdfc_card', bank_name: 'HDFC Bank Credit Card', account_type: 'credit_card' }, { key: 'sbi_card', bank_name: 'SBI Card', account_type: 'credit_card' },
  { key: 'generic', bank_name: 'Unknown Bank', account_type: 'bank' }, { key: 'generic_card', bank_name: 'Credit Card', account_type: 'credit_card' },
]

const PREVIEW = {
  upload: {
    id: 'up1', bank_name: 'State Bank of India', file_name: 'sbi_locked.pdf', parser_used: 'sbi:pdf', parsed_count: 45,
    duplicate_count: 0, total_debits: 83538, total_credits: 128319, warnings: [],
    date_range: { start: '2025-08-01', end: '2025-08-31' },
  },
  new_count: 45,
  uncategorized_count: 0,
  transactions: [{
    id: 't1', transaction_date: '2025-08-01', normalized_merchant: 'Acme', raw_description: 'BY TRANSFER-NEFT*ACME',
    category_name: 'Income', category_color: '#2F7D55', payment_method: 'NEFT', amount: 64000, transaction_type: 'credit',
    is_duplicate: false, needs_review: false,
  }],
}

function renderUpload() {
  api.get.mockImplementation((url) => Promise.resolve({ data: url === '/statements/banks' ? BANKS : [] }))
  return renderWithProviders(<FilterProvider><Upload /></FilterProvider>, { route: '/upload' })
}

const fileInput = () => document.querySelector('input[type=file]')
const choose = (name, type = 'application/pdf', size = 2048) => {
  const file = new File(['x'.repeat(size)], name, { type })
  fireEvent.change(fileInput(), { target: { files: [file] } })
  return file
}

beforeEach(() => {
  vi.mocked(api.get).mockReset()
  vi.mocked(api.post).mockReset()
})

describe('Upload page - file selection', () => {
  it('accepts CSV, PDF and Excel', () => {
    renderUpload()
    expect(fileInput()).toHaveAttribute('accept', expect.stringContaining('.xlsx'))
    expect(screen.getByText(/CSV, PDF or Excel · up to 10 MB/)).toBeInTheDocument()
  })

  it('rejects unsupported files before uploading', () => {
    renderUpload()
    choose('notes.txt', 'text/plain')
    expect(screen.getByRole('alert')).toHaveTextContent('Only CSV, PDF and Excel (.xls, .xlsx) statements are supported.')
    expect(screen.getByRole('button', { name: /analyse statement/i })).toBeDisabled()
  })

  it('rejects files over the size limit', () => {
    renderUpload()
    choose('huge.pdf', 'application/pdf', 11 * 1024 * 1024)
    expect(screen.getByRole('alert')).toHaveTextContent('File is larger than 10 MB.')
  })

  it('only offers a password field for PDFs', () => {
    renderUpload()
    choose('statement.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    expect(screen.queryByLabelText(/PDF password/i)).not.toBeInTheDocument()
    choose('statement.pdf')
    expect(screen.getByLabelText(/PDF password/i)).toHaveAttribute('type', 'password')
  })
})

describe('Upload page - password-protected PDF', () => {
  it('asks for the password, retries with it, then shows the preview', async () => {
    renderUpload()
    choose('sbi_locked.pdf')
    api.post.mockRejectedValueOnce(apiError(422, 'pdf_password_required', 'This PDF is password protected. Enter the statement password to unlock it.'))
    await userEvent.click(screen.getByRole('button', { name: /analyse statement/i }))

    expect(await screen.findByText('This statement is password protected')).toBeInTheDocument()
    const unlock = screen.getByRole('button', { name: /unlock & analyse/i })
    expect(unlock).toBeDisabled()
    // the panel re-mounts after each attempt, so always re-query the field
    const pw = () => screen.getByLabelText(/PDF password/i)
    await waitFor(() => expect(pw()).toHaveFocus())

    api.post.mockRejectedValueOnce(apiError(422, 'pdf_password_incorrect', 'The password is incorrect. Please check it and try again.'))
    await userEvent.type(pw(), '12345678')
    await userEvent.click(unlock)
    expect(await screen.findByText('Incorrect password')).toBeInTheDocument()

    api.post.mockResolvedValueOnce({ data: PREVIEW })
    expect(pw()).toHaveValue('12345678') // the typed password survives a failed attempt
    await userEvent.clear(pw())
    await userEvent.type(pw(), 'DEMO1234')
    await userEvent.click(screen.getByRole('button', { name: /unlock & analyse/i }))

    expect(await screen.findByText('State Bank of India')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /import 45 transactions/i })).toBeInTheDocument()

    const forms = api.post.mock.calls.map(([url, form]) => (expect(url).toBe('/statements/preview'), form))
    expect(forms[0].get('password')).toBeNull() // first attempt sends no password
    expect(forms[1].get('password')).toBe('12345678')
    expect(forms[2].get('password')).toBe('DEMO1234')
    expect(forms[2].get('file').name).toBe('sbi_locked.pdf')
  })

  it('never sends a password with non-PDF files', async () => {
    renderUpload()
    choose('hdfc.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    api.post.mockResolvedValueOnce({ data: { ...PREVIEW, upload: { ...PREVIEW.upload, bank_name: 'HDFC Bank', file_name: 'hdfc.xlsx' } } })
    await userEvent.click(screen.getByRole('button', { name: /analyse statement/i }))
    await screen.findByText('HDFC Bank', { selector: 'h2' })
    expect(api.post.mock.calls[0][1].get('password')).toBeNull()
  })
})

describe('Upload page - errors and import', () => {
  it('points to history when the statement was already imported', async () => {
    renderUpload()
    choose('hdfc.csv', 'text/csv')
    api.post.mockRejectedValueOnce(apiError(409, 'duplicate_statement', 'This statement file has already been imported.'))
    await userEvent.click(screen.getByRole('button', { name: /analyse statement/i }))
    expect(await screen.findByText('Already imported')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View statement history' })).toHaveAttribute('href', '/statements')
  })

  it('confirms the import and shows the result', async () => {
    renderUpload()
    choose('sbi.pdf')
    api.post
      .mockResolvedValueOnce({ data: PREVIEW })
      .mockResolvedValueOnce({ data: { id: 'up1', transaction_count: 45, duplicate_count: 0, bank_name: 'State Bank of India' } })
    await userEvent.click(screen.getByRole('button', { name: /analyse statement/i }))
    await userEvent.click(await screen.findByRole('button', { name: /import 45 transactions/i }))
    expect(api.post).toHaveBeenLastCalledWith('/statements/up1/confirm', { include_duplicates: false })
    expect(await screen.findByRole('heading', { name: 'Statement imported' })).toBeInTheDocument()
    expect(screen.getByText(/45 transactions from State Bank of India were added/)).toBeInTheDocument()
  })
})

describe('Upload page - credit cards', () => {
  const CARD_PREVIEW = {
    ...PREVIEW,
    upload: { ...PREVIEW.upload, bank_name: 'HDFC Bank Credit Card', file_name: 'card.csv', account_type: 'credit_card', parser_used: 'hdfc_card:csv' },
  }

  it('groups bank accounts and credit cards in the format list', async () => {
    renderUpload()
    const select = await screen.findByLabelText('Statement format')
    await waitFor(() => expect(within(select).getAllByRole('option').length).toBeGreaterThan(1))
    const groups = Object.fromEntries([...select.querySelectorAll('optgroup')].map((g) => [g.label, [...g.querySelectorAll('option')].map((o) => o.textContent)]))
    expect(groups['Bank accounts']).toEqual(['HDFC Bank', 'State Bank of India', 'Other bank (generic parser)'])
    expect(groups['Credit cards']).toEqual(['HDFC Bank Credit Card', 'SBI Card', 'Other credit card'])
    expect(within(select).getAllByRole('option')[0]).toHaveTextContent('Auto-detect (recommended)')
  })

  it('lists cards under supported formats', async () => {
    renderUpload()
    expect(await screen.findByText(/Credit cards: HDFC Bank, SBI Card and other issuers/)).toBeInTheDocument()
  })

  it('sends the chosen card format and labels the preview as a credit card', async () => {
    renderUpload()
    choose('card.csv', 'text/csv')
    await waitFor(() => expect(within(screen.getByLabelText('Statement format')).getAllByRole('option').length).toBeGreaterThan(1))
    await userEvent.selectOptions(screen.getByLabelText('Statement format'), 'hdfc_card')
    api.post.mockResolvedValueOnce({ data: CARD_PREVIEW })
    await userEvent.click(screen.getByRole('button', { name: /analyse statement/i }))

    expect(api.post.mock.calls[0][1].get('bank')).toBe('hdfc_card')
    expect(await screen.findByRole('heading', { name: /HDFC Bank Credit Card/ })).toHaveTextContent('Credit card')
    expect(screen.getByText(/Payments you make to the card are filed under Credit Card Payments and are not counted as income/)).toBeInTheDocument()
  })

  it('does not show the card note or badge for a bank statement', async () => {
    renderUpload()
    choose('sbi.pdf')
    api.post.mockResolvedValueOnce({ data: { ...PREVIEW, upload: { ...PREVIEW.upload, account_type: 'bank' } } })
    await userEvent.click(screen.getByRole('button', { name: /analyse statement/i }))
    expect(await screen.findByRole('heading', { name: 'State Bank of India' })).not.toHaveTextContent('Credit card')
    expect(screen.queryByText(/not counted as income/)).not.toBeInTheDocument()
  })
})
