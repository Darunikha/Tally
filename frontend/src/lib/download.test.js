import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, errorMessage } from '../api/client'
import { downloadFile, filenameFrom } from './download'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn() } }
})

describe('filenameFrom', () => {
  it('reads quoted and unquoted names', () => {
    expect(filenameFrom('attachment; filename="tally-transactions-2025-08.csv"', 'x')).toBe('tally-transactions-2025-08.csv')
    expect(filenameFrom('attachment; filename=report.pdf', 'x')).toBe('report.pdf')
    expect(filenameFrom('attachment; filename="my report.pdf"', 'x')).toBe('my report.pdf')
  })
  it('falls back when the header is missing or unhelpful', () => {
    expect(filenameFrom(undefined, 'fallback.csv')).toBe('fallback.csv')
    expect(filenameFrom('attachment', 'fallback.csv')).toBe('fallback.csv')
  })
  it('refuses names that look like paths', () => {
    expect(filenameFrom('attachment; filename="../../etc/passwd"', 'safe.csv')).toBe('safe.csv')
    expect(filenameFrom('attachment; filename="a\\b.csv"', 'safe.csv')).toBe('safe.csv')
  })
})

describe('downloadFile', () => {
  let click
  beforeEach(() => {
    api.get.mockReset()
    click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { click.lastAnchor = this })
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:file')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  })
  afterEach(() => { vi.useRealTimers() }) // only the revoke test fakes timers: jsdom's FileReader needs real ones

  it('requests a blob with the filters (empty ones dropped) and saves it under the server name', async () => {
    api.get.mockResolvedValue({ data: new Blob(['a,b']), headers: { 'content-disposition': 'attachment; filename="tally-transactions-2025-08.csv"' } })
    const name = await downloadFile('/transactions/export', { month: 8, year: 2025, search: '', category_id: undefined, format: 'csv' }, 'fallback.csv')
    expect(api.get).toHaveBeenCalledWith('/transactions/export', { params: { month: 8, year: 2025, format: 'csv' }, responseType: 'blob' })
    expect(name).toBe('tally-transactions-2025-08.csv')
    expect(click).toHaveBeenCalledTimes(1)
    expect(click.lastAnchor.download).toBe('tally-transactions-2025-08.csv')
    expect(click.lastAnchor.href).toBe('blob:file')
    expect(document.querySelector('a[download]')).toBeNull() // the temporary link is removed again
  })

  it('uses the fallback name when the browser cannot see the header', async () => {
    api.get.mockResolvedValue({ data: new Blob(['x']), headers: {} })
    expect(await downloadFile('/reports/summary.pdf', {}, 'tally-report.pdf')).toBe('tally-report.pdf')
  })

  it('releases the object URL shortly afterwards', async () => {
    vi.useFakeTimers()
    api.get.mockResolvedValue({ data: new Blob(['x']), headers: {} })
    await downloadFile('/x', {}, 'x.csv')
    expect(URL.revokeObjectURL).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1100)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:file')
  })

  it('turns a blob error response back into the API message', async () => {
    const body = { error: { code: 'too_many_rows', message: 'That is 60,000 transactions. Narrow the date range and try again.' } }
    api.get.mockRejectedValue(Object.assign(new Error('Request failed'), { response: { status: 400, data: new Blob([JSON.stringify(body)], { type: 'application/json' }) } }))
    const err = await downloadFile('/transactions/export', {}, 'x.csv').catch((e) => e)
    expect(errorMessage(err)).toBe('That is 60,000 transactions. Narrow the date range and try again.')
    expect(click).not.toHaveBeenCalled()
  })

  it('keeps a generic message when the error body is not JSON', async () => {
    api.get.mockRejectedValue(Object.assign(new Error('Request failed'), { response: { status: 500, data: new Blob(['<html>oops</html>']) } }))
    const err = await downloadFile('/x', {}, 'x.csv').catch((e) => e)
    expect(errorMessage(err, 'Export failed')).toBe('Export failed')
  })
})
