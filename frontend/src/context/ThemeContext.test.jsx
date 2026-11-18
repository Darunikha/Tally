import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ThemeToggle from '../components/ThemeToggle'
import { THEME_KEY, ThemeProvider, useTheme } from './ThemeContext'

const original = window.matchMedia
function deviceTheme(dark) {
  let handler
  const mq = { matches: dark, addEventListener: (_, h) => { handler = h }, removeEventListener: () => { handler = null } }
  window.matchMedia = vi.fn(() => mq)
  return { change: (nowDark) => { mq.matches = nowDark; handler?.({ matches: nowDark }) }, listening: () => !!handler }
}

function Show() {
  const { preference, resolved, setPreference } = useTheme()
  return (
    <>
      <output data-testid="state">{preference}/{resolved}</output>
      {['light', 'dark', 'system', 'bogus'].map((p) => <button key={p} onClick={() => setPreference(p)}>{`set ${p}`}</button>)}
    </>
  )
}
const mount = (ui = <Show />) => render(<ThemeProvider>{ui}</ThemeProvider>)
const isDark = () => document.documentElement.classList.contains('dark')

beforeEach(() => {
  localStorage.clear()
  document.documentElement.classList.remove('dark')
  document.head.insertAdjacentHTML('beforeend', '<meta name="theme-color" content="#F6F6F1">')
})
afterEach(() => {
  window.matchMedia = original
  document.querySelector('meta[name="theme-color"]')?.remove()
  vi.restoreAllMocks()
})

describe('ThemeProvider', () => {
  it('follows a dark device by default', () => {
    deviceTheme(true)
    mount()
    expect(screen.getByTestId('state')).toHaveTextContent('system/dark')
    expect(isDark()).toBe(true)
  })

  it('follows a light device by default', () => {
    deviceTheme(false)
    mount()
    expect(screen.getByTestId('state')).toHaveTextContent('system/light')
    expect(isDark()).toBe(false)
  })

  it('lets a saved choice beat the device', () => {
    deviceTheme(false)
    localStorage.setItem(THEME_KEY, 'dark')
    mount()
    expect(screen.getByTestId('state')).toHaveTextContent('dark/dark')
    expect(isDark()).toBe(true)
  })

  it('ignores a corrupted saved value', () => {
    deviceTheme(true)
    localStorage.setItem(THEME_KEY, 'neon')
    mount()
    expect(screen.getByTestId('state')).toHaveTextContent('system/dark')
  })

  it('remembers the choice, and "match device" forgets it', async () => {
    deviceTheme(false)
    mount()
    await userEvent.click(screen.getByRole('button', { name: 'set dark' }))
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    expect(isDark()).toBe(true)
    await userEvent.click(screen.getByRole('button', { name: 'set light' }))
    expect(localStorage.getItem(THEME_KEY)).toBe('light')
    expect(isDark()).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: 'set system' }))
    expect(localStorage.getItem(THEME_KEY)).toBeNull()
  })

  it('ignores an unknown choice', async () => {
    deviceTheme(false)
    mount()
    await userEvent.click(screen.getByRole('button', { name: 'set bogus' }))
    expect(screen.getByTestId('state')).toHaveTextContent('system/light')
    expect(localStorage.getItem(THEME_KEY)).toBeNull()
  })

  it('switches live when the device switches, but only while following the device', async () => {
    const device = deviceTheme(false)
    mount()
    act(() => device.change(true))
    expect(screen.getByTestId('state')).toHaveTextContent('system/dark')
    expect(isDark()).toBe(true)
    await userEvent.click(screen.getByRole('button', { name: 'set light' }))
    act(() => device.change(true))
    expect(screen.getByTestId('state')).toHaveTextContent('light/light') // an explicit choice stays put
    expect(isDark()).toBe(false)
  })

  it('stops listening to the device when it unmounts', () => {
    const device = deviceTheme(false)
    const { unmount } = mount()
    expect(device.listening()).toBe(true)
    unmount()
    expect(device.listening()).toBe(false)
  })

  it('colours the phone status bar to match', async () => {
    deviceTheme(false)
    mount()
    const color = () => document.querySelector('meta[name="theme-color"]').getAttribute('content')
    expect(color()).toBe('#F6F6F1')
    await userEvent.click(screen.getByRole('button', { name: 'set dark' }))
    expect(color()).toBe('#0E1411')
  })

  it('still works when browser storage is blocked', async () => {
    deviceTheme(true)
    vi.spyOn(localStorage, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    mount()
    expect(screen.getByTestId('state')).toHaveTextContent('system/dark')
    await userEvent.click(screen.getByRole('button', { name: 'set light' }))
    expect(screen.getByTestId('state')).toHaveTextContent('light/light')
  })

  it('behaves as light mode outside a provider', () => {
    render(<Show />)
    expect(screen.getByTestId('state')).toHaveTextContent('light/light')
  })
})

describe('ThemeToggle', () => {
  const open = () => userEvent.click(screen.getByRole('button', { name: /^Theme:/ }))

  it('names the current choice', () => {
    deviceTheme(false)
    mount(<ThemeToggle />)
    expect(screen.getByRole('button', { name: 'Theme: Match device' })).toBeInTheDocument()
  })

  it('offers light, dark and match device, marking the current one', async () => {
    deviceTheme(false)
    localStorage.setItem(THEME_KEY, 'dark')
    mount(<ThemeToggle />)
    await open()
    const items = screen.getAllByRole('menuitemradio')
    expect(items.map((i) => i.textContent)).toEqual(['Light', 'Dark', 'Match device'])
    expect(items.map((i) => i.getAttribute('aria-checked'))).toEqual(['false', 'true', 'false'])
  })

  it('applies a choice and closes', async () => {
    deviceTheme(false)
    mount(<ThemeToggle />)
    await open()
    await userEvent.click(screen.getByRole('menuitemradio', { name: 'Dark' }))
    expect(isDark()).toBe(true)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Theme: Dark' })).toBeInTheDocument()
  })

  it('closes with Escape', async () => {
    deviceTheme(false)
    mount(<ThemeToggle />)
    await open()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })
})
