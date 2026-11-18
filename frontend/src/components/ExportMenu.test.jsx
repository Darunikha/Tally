import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { downloadFile } from '../lib/download'
import { apiError, renderWithProviders } from '../test/utils'
import DownloadReportButton from './DownloadReportButton'
import ExportMenu from './ExportMenu'

vi.mock('../lib/download', () => ({ downloadFile: vi.fn() }))

beforeEach(() => { downloadFile.mockReset() })

const open = async () => userEvent.click(screen.getByRole('button', { name: /export/i }))

describe('ExportMenu', () => {
  it('is closed until opened, then says how much it will export', async () => {
    renderWithProviders(<ExportMenu params={{}} total={12345} />)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    await open()
    expect(screen.getByRole('menu', { name: 'Export format' })).toHaveTextContent('Exports all 12,345 transactions matching your filters.')
    expect(screen.getAllByRole('menuitem').map((i) => i.textContent)).toEqual([
      'CSVPlain table, opens anywhere', 'ExcelDates and amounts ready to sort and sum',
    ])
  })

  it('speaks in the singular and copes with an unknown total', async () => {
    const { unmount } = renderWithProviders(<ExportMenu params={{}} total={1} />)
    await open()
    expect(screen.getByRole('menu')).toHaveTextContent('Exports all 1 transaction matching your filters.')
    unmount()
    renderWithProviders(<ExportMenu params={{}} />)
    await open()
    expect(screen.getByRole('menu')).toHaveTextContent('Exports every transaction matching your filters.')
  })

  it.each([['CSV', 'csv'], ['Excel', 'xlsx']])('downloads %s with the page filters', async (label, format) => {
    downloadFile.mockResolvedValue(`tally-transactions-2025-08.${format}`)
    renderWithProviders(<ExportMenu params={{ category_id: 'c1', month: 8, year: 2025 }} total={5} />)
    await open()
    await userEvent.click(screen.getByRole('menuitem', { name: new RegExp(label) }))
    expect(downloadFile).toHaveBeenCalledWith('/transactions/export', { category_id: 'c1', month: 8, year: 2025, format }, `tally-transactions.${format}`)
    expect(await screen.findByText(`Downloaded tally-transactions-2025-08.${format}`)).toBeInTheDocument()
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('shows the API reason when the export is refused and lets you try again', async () => {
    downloadFile.mockRejectedValue(apiError(400, 'too_many_rows', 'That is 60,000 transactions. Narrow the date range and try again.'))
    renderWithProviders(<ExportMenu params={{}} total={60000} />)
    await open()
    await userEvent.click(screen.getByRole('menuitem', { name: /CSV/ }))
    expect(await screen.findByText(/Narrow the date range and try again/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /export/i })).toBeEnabled()
  })

  it('is disabled while an export is running', async () => {
    let finish
    downloadFile.mockReturnValue(new Promise((r) => { finish = r }))
    renderWithProviders(<ExportMenu params={{}} total={5} />)
    await open()
    await userEvent.click(screen.getByRole('menuitem', { name: /Excel/ }))
    expect(screen.getByRole('button', { name: /exporting/i })).toBeDisabled()
    finish('done.xlsx')
    await waitFor(() => expect(screen.getByRole('button', { name: /export/i })).toBeEnabled())
  })

  it('closes with Escape', async () => {
    renderWithProviders(<ExportMenu params={{}} total={5} />)
    await open()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })
})

describe('DownloadReportButton', () => {
  it('downloads the PDF for the chosen period', async () => {
    downloadFile.mockResolvedValue('tally-report-2025-10.pdf')
    renderWithProviders(<DownloadReportButton params={{ month: 10, year: 2025, upload_id: 'u1' }} />)
    await userEvent.click(screen.getByRole('button', { name: /report/i }))
    expect(downloadFile).toHaveBeenCalledWith('/reports/summary.pdf', { month: 10, year: 2025, upload_id: 'u1' }, 'tally-report.pdf')
    expect(await screen.findByText('Downloaded tally-report-2025-10.pdf')).toBeInTheDocument()
  })

  it('reports a failure without getting stuck', async () => {
    downloadFile.mockRejectedValue(apiError(429, 'rate_limited', 'Too many requests. Try again in 20 minutes.'))
    renderWithProviders(<DownloadReportButton params={{}} />)
    await userEvent.click(screen.getByRole('button', { name: /report/i }))
    expect(await screen.findByText(/Try again in 20 minutes/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /report/i })).toBeEnabled()
  })
})
