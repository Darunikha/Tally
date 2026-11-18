import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../context/ToastContext'

/**
 * Render a component inside the app's real providers and a router.
 * `extraRoutes` lets a test assert navigation, e.g. { '/login': <p>login page</p> }.
 */
export function renderWithProviders(ui, { route = '/', path = '*', extraRoutes = {} } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path={path} element={ui} />
            {Object.entries(extraRoutes).map(([p, el]) => <Route key={p} path={p} element={el} />)}
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </MemoryRouter>,
  )
}

/** An axios-style error as the API client would reject with. */
export function apiError(status, code, message, details) {
  const err = new Error(message)
  err.response = { status, data: { error: { code, message, details } } }
  return err
}

const STANDARD_GETS = {
  '/auth/me': { id: 'u1', full_name: 'Dee', email: 'dee@example.com' },
  '/analytics/periods': { months: [], latest: null, today: '2026-11-18' },
  '/analytics/statements-filter': [],
  '/accounts': { accounts: [], unassigned: null, totals: {} },
}

/**
 * Sign in and answer the endpoints every page loads through the filter context. `overrides` maps URL -> response
 * body (or an Error to reject with, or a function of the URL's params). Anything else is rejected loudly.
 * Pass the mocked `api` and the real `tokenStore` from the test's own import of '../api/client'.
 */
export function mockSignedInApi(api, tokenStore, overrides = {}) {
  tokenStore.set('test-token')
  const routes = { ...STANDARD_GETS, ...overrides }
  api.get.mockImplementation((url, config) => {
    if (!(url in routes)) return Promise.reject(new Error(`unexpected GET ${url}`))
    const v = typeof routes[url] === 'function' ? routes[url](config?.params) : routes[url]
    return v instanceof Error ? Promise.reject(v) : Promise.resolve({ data: v })
  })
}
