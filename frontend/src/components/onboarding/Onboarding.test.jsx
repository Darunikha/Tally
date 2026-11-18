import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, tokenStore } from '../../api/client'
import { FilterProvider } from '../../context/FilterContext'
import { apiError, mockSignedInApi, renderWithProviders } from '../../test/utils'
import DemoDataButton from './DemoDataButton'
import GettingStarted from './GettingStarted'
import NoStatementsYet from './NoStatementsYet'
import WelcomeTour from './WelcomeTour'

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }
})

beforeEach(() => {
  sessionStorage.clear()
  for (const m of [api.get, api.post, api.patch, api.put, api.delete]) m.mockReset()
})

const step = (key, done, o = {}) => ({ key, done, title: `Step ${key}`, description: `Do ${key}`, href: `/${key}`, ...o })
const ONBOARDING = (done = [], extra = {}) => ({
  steps: ['statement', 'account', 'review', 'budget'].map((k) => step(k, done.includes(k))),
  completed: done.length, total: 4, welcome_seen: true, checklist_dismissed: false, show_checklist: true, ...extra,
})
const mount = (ui, overrides) => {
  mockSignedInApi(api, tokenStore, overrides)
  return renderWithProviders(<FilterProvider>{ui}</FilterProvider>, { extraRoutes: { '/upload': <p>Upload page</p> } })
}

describe('GettingStarted', () => {
  it('shows progress and what is left', () => {
    mount(<GettingStarted onboarding={ONBOARDING(['statement'])} onHide={() => {}} />)
    expect(screen.getByText('1 of 4 done')).toBeInTheDocument()
    const bar = screen.getByRole('progressbar', { name: 'Getting started progress' })
    expect(bar).toHaveAttribute('aria-valuenow', '1')
    expect(bar).toHaveAttribute('aria-valuemax', '4')
    expect(screen.getAllByLabelText('Done')).toHaveLength(1)
    expect(screen.getAllByLabelText('Not done yet')).toHaveLength(3)
  })

  it('only describes and links the steps that are not done', () => {
    mount(<GettingStarted onboarding={ONBOARDING(['statement'])} onHide={() => {}} />)
    expect(screen.queryByText('Do statement')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Step statement: go' })).not.toBeInTheDocument()
    expect(screen.getByText('Do account')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Step account: go' })).toHaveAttribute('href', '/account')
    expect(screen.getByRole('link', { name: 'Step budget: go' })).toHaveAttribute('href', '/budget')
  })

  it('emphasises only the next step', () => {
    mount(<GettingStarted onboarding={ONBOARDING(['statement'])} onHide={() => {}} />)
    expect(screen.getByRole('link', { name: 'Step account: go' })).toHaveClass('btn-primary')
    expect(screen.getByRole('link', { name: 'Step review: go' })).toHaveClass('btn-secondary')
  })

  it('hides on request', async () => {
    const onHide = vi.fn()
    mount(<GettingStarted onboarding={ONBOARDING()} onHide={onHide} />)
    await userEvent.click(screen.getByRole('button', { name: 'Hide the getting started checklist' }))
    expect(onHide).toHaveBeenCalledTimes(1)
  })
})

describe('DemoDataButton', () => {
  it('loads the demo, says how much, and refreshes the app', async () => {
    mount(<DemoDataButton />)
    api.post.mockResolvedValueOnce({ data: { imported: [{ file_name: 'a', transactions: 133 }, { file_name: 'b', transactions: 100 }] } })
    const before = api.get.mock.calls.length
    await userEvent.click(screen.getByRole('button', { name: /try with demo data/i }))
    expect(api.post).toHaveBeenCalledWith('/settings/demo-data')
    expect(await screen.findByText(/233 sample transactions loaded/)).toBeInTheDocument()
    await waitFor(() => expect(api.get.mock.calls.length).toBeGreaterThan(before)) // the filter context reloads its lists
  })

  it('says so when the demo was already loaded', async () => {
    mount(<DemoDataButton />)
    api.post.mockResolvedValueOnce({ data: { imported: [] } })
    await userEvent.click(screen.getByRole('button', { name: /try with demo data/i }))
    expect(await screen.findByText('Demo data is already loaded.')).toBeInTheDocument()
  })

  it('tells the caller when it is done', async () => {
    const onLoaded = vi.fn()
    mount(<DemoDataButton onLoaded={onLoaded} />)
    api.post.mockResolvedValueOnce({ data: { imported: [{ transactions: 5 }] } })
    await userEvent.click(screen.getByRole('button', { name: /try with demo data/i }))
    await waitFor(() => expect(onLoaded).toHaveBeenCalled())
  })

  it('shows the reason on failure and can be tried again', async () => {
    const onLoaded = vi.fn()
    mount(<DemoDataButton onLoaded={onLoaded} />)
    api.post.mockRejectedValueOnce(apiError(403, 'email_not_verified', 'Please verify your email first.'))
    await userEvent.click(screen.getByRole('button', { name: /try with demo data/i }))
    expect(await screen.findByText('Please verify your email first.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try with demo data/i })).toBeEnabled()
    expect(onLoaded).not.toHaveBeenCalled()
  })

  it('is disabled while loading', async () => {
    mount(<DemoDataButton />)
    let finish
    api.post.mockReturnValueOnce(new Promise((r) => { finish = r }))
    await userEvent.click(screen.getByRole('button', { name: /try with demo data/i }))
    expect(screen.getByRole('button', { name: /loading/i })).toBeDisabled()
    finish({ data: { imported: [] } })
    await waitFor(() => expect(screen.getByRole('button', { name: /try with demo data/i })).toBeEnabled())
  })
})

describe('NoStatementsYet', () => {
  it('offers the two ways forward', () => {
    mount(<NoStatementsYet message="Custom words for this page." />)
    expect(screen.getByRole('heading', { name: 'Add your first statement' })).toBeInTheDocument()
    expect(screen.getByText('Custom words for this page.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /upload a statement/i })).toHaveAttribute('href', '/upload')
    expect(screen.getByRole('button', { name: /try with demo data/i })).toBeInTheDocument()
    expect(screen.getByText(/password-protected e-statements/)).toBeInTheDocument()
  })
})

describe('WelcomeTour', () => {
  const tour = (onFinish = vi.fn()) => { mount(<WelcomeTour firstName="Dee" onFinish={onFinish} />); return onFinish }
  const dialog = () => screen.getByRole('dialog')

  it('greets by name and starts at the first of three steps', () => {
    tour()
    expect(dialog()).toHaveAccessibleName('Welcome to Tally, Dee')
    expect(within(dialog()).getByRole('heading', { name: 'Bring in a statement' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Step 1 of 3' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Back' })).not.toBeInTheDocument()
  })

  it('moves forward and back through the steps', async () => {
    tour()
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByRole('heading', { name: 'Tally does the sorting' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByRole('heading', { name: 'Private by design' })).toBeInTheDocument()
    expect(screen.getByText(/never connects to your bank/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /back/i }))
    expect(screen.getByRole('heading', { name: 'Tally does the sorting' })).toBeInTheDocument()
  })

  it('jumps straight to a step from the dots', async () => {
    tour()
    await userEvent.click(screen.getByRole('button', { name: 'Go to step 3: Private by design' }))
    expect(screen.getByRole('heading', { name: 'Private by design' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Go to step 3: Private by design' })).toHaveAttribute('aria-current', 'step')
  })

  it('only offers the real actions on the last step', async () => {
    tour()
    expect(screen.queryByRole('button', { name: /upload a statement/i })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Go to step 3: Private by design' }))
    expect(screen.getByRole('button', { name: /upload a statement/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try with demo data/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /next/i })).not.toBeInTheDocument()
  })

  it('counts every way out as finished, so it is not shown again', async () => {
    let onFinish = tour()
    await userEvent.click(screen.getByRole('button', { name: 'Skip for now' }))
    expect(onFinish).toHaveBeenCalledTimes(1)
  })

  it('finishes when closed with the X or Escape', async () => {
    const onFinish = tour()
    await userEvent.click(within(dialog()).getByRole('button', { name: 'Close' }))
    await userEvent.keyboard('{Escape}')
    expect(onFinish).toHaveBeenCalledTimes(2)
  })

  it('finishes and goes to the upload page', async () => {
    const onFinish = tour()
    await userEvent.click(screen.getByRole('button', { name: 'Go to step 3: Private by design' }))
    await userEvent.click(screen.getByRole('button', { name: /upload a statement/i }))
    expect(onFinish).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('Upload page')).toBeInTheDocument()
  })

  it('finishes after loading the demo', async () => {
    const onFinish = tour()
    api.post.mockResolvedValueOnce({ data: { imported: [{ transactions: 12 }] } })
    await userEvent.click(screen.getByRole('button', { name: 'Go to step 3: Private by design' }))
    await userEvent.click(screen.getByRole('button', { name: /try with demo data/i }))
    await waitFor(() => expect(onFinish).toHaveBeenCalledTimes(1))
  })
})
