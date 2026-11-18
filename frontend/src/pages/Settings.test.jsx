import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, tokenStore } from '../api/client'
import { FilterProvider } from '../context/FilterContext'
import { THEME_KEY, ThemeProvider } from '../context/ThemeContext'
import { mockSignedInApi, renderWithProviders } from '../test/utils'
import SettingsPage from './Settings'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }
})

beforeEach(() => {
  sessionStorage.clear(); localStorage.clear()
  document.documentElement.classList.remove('dark')
  for (const m of [api.get, api.post, api.patch, api.put, api.delete]) m.mockReset()
})

function renderSettings() {
  mockSignedInApi(api, tokenStore, { '/settings/data-summary': { statements: 0, demo_statements: 0, transactions: 0, custom_rules: 0, custom_categories: 0, demo_available: true } })
  return renderWithProviders(<ThemeProvider><FilterProvider><SettingsPage /></FilterProvider></ThemeProvider>, { route: '/settings' })
}

describe('Settings - appearance', () => {
  it('renders the page (a missing import here once blanked the whole page)', async () => {
    renderSettings()
    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.getByText('Appearance')).toBeInTheDocument()
  })

  it('switches to dark and remembers it', async () => {
    renderSettings()
    await userEvent.click(await screen.findByRole('tab', { name: 'Dark' }))
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    expect(screen.getByRole('tab', { name: 'Dark' })).toHaveAttribute('aria-selected', 'true')
  })

  it('goes back to light', async () => {
    localStorage.setItem(THEME_KEY, 'dark')
    renderSettings()
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    await userEvent.click(await screen.findByRole('tab', { name: 'Light' }))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('offers matching the device', async () => {
    localStorage.setItem(THEME_KEY, 'dark')
    renderSettings()
    await userEvent.click(await screen.findByRole('tab', { name: 'Match device' }))
    expect(localStorage.getItem(THEME_KEY)).toBeNull()
  })
})
