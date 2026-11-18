import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CategoryDonut, foldCategories, SERIES } from './charts'
import CardPaymentsNote from './CardPaymentsNote'
import { ConfirmDialog, Delta, Pagination, SeverityBadge, TypeBadge } from './ui'

const cat = (name, amount, percentage, count = 1) => ({ name, amount, percentage, count, color: '#123456' })

describe('foldCategories (donut legend)', () => {
  it('keeps up to max+1 categories unchanged', () => {
    const rows = [cat('A', 60, 60), cat('B', 40, 40)]
    expect(foldCategories(rows, 5)).toBe(rows)
  })
  it('folds the tail into a grey "Others" slice, keeping colours of the top ones', () => {
    const rows = [cat('A', 50, 50), cat('B', 20, 20), cat('C', 10, 10), cat('D', 10, 10), cat('E', 6, 6), cat('F', 4, 4)]
    const out = foldCategories(rows, 3)
    expect(out.map((r) => r.name)).toEqual(['A', 'B', 'C', 'Others'])
    expect(out[3]).toMatchObject({ amount: 20, percentage: 20, count: 3, color: SERIES.muted, folded: ['D', 'E', 'F'] })
    expect(out[0].color).toBe('#123456')
  })
})

describe('Delta', () => {
  it('colours increases by whether up is good', () => {
    const { rerender } = render(<Delta value={12} goodWhenUp />)
    expect(screen.getByText('12%').closest('span')).toHaveClass('text-brand-600')
    rerender(<Delta value={12} goodWhenUp={false} />)
    expect(screen.getByText('12%').closest('span')).toHaveClass('text-danger-500')
  })
  it('shows one decimal for small changes and a note when there is no comparison', () => {
    const { rerender } = render(<Delta value={-2.345} />)
    expect(screen.getByText('2.3%')).toBeInTheDocument()
    rerender(<Delta value={null} />)
    expect(screen.getByText('No prior data')).toBeInTheDocument()
  })
})

describe('badges', () => {
  it('labels transaction types and severities in text, not colour alone', () => {
    render(<><TypeBadge type="credit" /><TypeBadge type="debit" /><SeverityBadge severity="high" /></>)
    expect(screen.getByText('Credit')).toBeInTheDocument()
    expect(screen.getByText('Debit')).toBeInTheDocument()
    expect(screen.getByText('High')).toBeInTheDocument()
  })
})

describe('Pagination', () => {
  it('shows the range and moves between pages', async () => {
    const onPage = vi.fn()
    render(<Pagination page={2} pages={6} total={133} pageSize={25} onPage={onPage} />)
    expect(screen.getByText('26–50')).toBeInTheDocument()
    expect(screen.getByText('2 / 6')).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('Next page'))
    await userEvent.click(screen.getByLabelText('Previous page'))
    expect(onPage.mock.calls).toEqual([[3], [1]])
  })
  it('disables navigation at the ends and hides when empty', () => {
    const { rerender, container } = render(<Pagination page={1} pages={1} total={3} pageSize={25} onPage={() => {}} />)
    expect(screen.getByLabelText('Previous page')).toBeDisabled()
    expect(screen.getByLabelText('Next page')).toBeDisabled()
    rerender(<Pagination page={1} pages={1} total={0} pageSize={25} onPage={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('ConfirmDialog', () => {
  it('confirms, cancels and closes on Escape', async () => {
    const onConfirm = vi.fn()
    const onClose = vi.fn()
    render(<ConfirmDialog open title="Delete statement?" message="This cannot be undone." confirmLabel="Delete" danger onConfirm={onConfirm} onClose={onClose} />)
    expect(screen.getByRole('dialog', { name: 'Delete statement?' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await userEvent.keyboard('{Escape}')
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(2)
  })
  it('renders nothing when closed', () => {
    render(<ConfirmDialog open={false} title="x" message="y" onConfirm={() => {}} onClose={() => {}} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('CardPaymentsNote', () => {
  it('says nothing when no payments are left out', () => {
    const { container } = render(<CardPaymentsNote count={0} />)
    expect(container).toBeEmptyDOMElement()
    render(<CardPaymentsNote />)
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })
  it('explains the difference between dashboard totals and the transaction list', () => {
    const { rerender } = render(<CardPaymentsNote count={1} />)
    expect(screen.getByRole('note')).toHaveTextContent('1 credit card bill payment is left out of income and spending')
    expect(screen.getByRole('note')).toHaveTextContent('see it on the Transactions page')
    rerender(<CardPaymentsNote count={3} />)
    expect(screen.getByRole('note')).toHaveTextContent('3 credit card bill payments are left out')
    expect(screen.getByRole('note')).toHaveTextContent('see them on the Transactions page')
  })
})


describe('CategoryDonut legend', () => {
  const rows = [cat('Shopping', 56863, 56), cat('Transportation', 2353, 2.3), cat('Rent', 18000, 17.6)]

  it('gives each category its name, amount and share, with the amount under the name so long names keep their room', () => {
    render(<CategoryDonut rows={rows} total={77216} />)
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent('Shopping')
    expect(items[0]).toHaveTextContent('₹56,863')
    expect(items[0]).toHaveTextContent('56%')
    const name = within(items[1]).getByText('Transportation')
    const amount = within(items[1]).getByText('₹2,353')
    expect(name.parentElement).toBe(amount.parentElement)   // same stacked cell, not competing for one row
    expect(name).toHaveClass('block')
  })

  it('shows the total in the middle', () => {
    render(<CategoryDonut rows={rows} total={77216} />)
    expect(screen.getByText('₹77,216')).toBeInTheDocument()
    expect(screen.getByText('Total')).toBeInTheDocument()
  })
})
