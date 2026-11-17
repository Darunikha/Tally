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
