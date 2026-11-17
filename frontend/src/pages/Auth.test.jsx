import { StrictMode } from 'react'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { apiError, renderWithProviders } from '../test/utils'
import { ForgotPassword, Login, Register, ResetPassword, VerifyEmail } from './Auth'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }
})

const session = { access_token: 'tok-123', token_type: 'bearer', user: { id: 'u1', full_name: 'Darunikha Sharma', email: 'd@x.com' } }

beforeEach(() => {
  vi.mocked(api.post).mockReset()
  vi.mocked(api.get).mockReset()
})

describe('Login', () => {
  it('signs in and stores the session token', async () => {
    api.post.mockResolvedValue({ data: session })
    renderWithProviders(<Login />, { route: '/login' })
    await userEvent.type(screen.getByLabelText('Email'), 'd@x.com')
    await userEvent.type(screen.getByLabelText('Password'), 'secret123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(api.post).toHaveBeenCalledWith('/auth/login', { email: 'd@x.com', password: 'secret123' })
    await waitFor(() => expect(sessionStorage.getItem('tally_token')).toBe('tok-123'))
  })

  it('shows the server error, including rate limiting', async () => {
    api.post.mockRejectedValue(apiError(429, 'rate_limited', 'Too many attempts. Please try again in 4 minutes.'))
    renderWithProviders(<Login />, { route: '/login' })
    await userEvent.type(screen.getByLabelText('Email'), 'd@x.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts. Please try again in 4 minutes.')
    expect(sessionStorage.getItem('tally_token')).toBeNull()
  })

  it('links to forgot password, carrying the typed email', async () => {
    renderWithProviders(<Login />, { route: '/login' })
    await userEvent.type(screen.getByLabelText('Email'), 'd@x.com')
    expect(screen.getByRole('link', { name: 'Forgot password?' })).toHaveAttribute('href', '/forgot-password?email=d%40x.com')
  })
})

describe('Register', () => {
  it('requires consent to the Terms and Privacy Policy before creating an account', async () => {
    api.post.mockResolvedValue({ data: session })
    renderWithProviders(<Register />, { route: '/register' })
    await userEvent.type(screen.getByLabelText('Full name'), 'Darunikha Sharma')
    await userEvent.type(screen.getByLabelText('Email'), 'd@x.com')
    await userEvent.type(screen.getByLabelText('Password'), 'secret123')
    const submit = screen.getByRole('button', { name: /create account/i })
    expect(submit).toBeDisabled()
    const consent = screen.getByRole('checkbox').closest('label')
    expect(within(consent).getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute('href', '/privacy')
    expect(within(consent).getByRole('link', { name: 'Terms of Service' })).toHaveAttribute('href', '/terms')

    await userEvent.click(screen.getByRole('checkbox'))
    expect(submit).toBeEnabled()
    await userEvent.click(submit)
    expect(api.post).toHaveBeenCalledWith('/auth/register', {
      full_name: 'Darunikha Sharma', email: 'd@x.com', password: 'secret123', accept_terms: true,
    })
  })
})

describe('ForgotPassword', () => {
  it('prefills the email and shows the generic confirmation', async () => {
    const message = "If an account exists for that email, we've sent a link to reset the password."
    api.post.mockResolvedValue({ data: { ok: true, message } })
    renderWithProviders(<ForgotPassword />, { route: '/forgot-password?email=d%40x.com' })
    expect(screen.getByLabelText('Email')).toHaveValue('d@x.com')
    await userEvent.click(screen.getByRole('button', { name: /send reset link/i }))
    expect(api.post).toHaveBeenCalledWith('/auth/forgot-password', { email: 'd@x.com' })
    expect(await screen.findByText('Check your inbox')).toBeInTheDocument()
    expect(screen.getByText(message)).toBeInTheDocument()
  })
})

describe('ResetPassword', () => {
  it('explains an incomplete link', () => {
    renderWithProviders(<ResetPassword />, { route: '/reset-password' })
    expect(screen.getByText('Link incomplete')).toBeInTheDocument()
  })

  it('checks the confirmation locally before calling the API', async () => {
    renderWithProviders(<ResetPassword />, { route: '/reset-password?token=abc123def456' })
    await userEvent.type(screen.getByLabelText('New password'), 'newpass456')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'different1')
    await userEvent.click(screen.getByRole('button', { name: /update password/i }))
    expect(screen.getByRole('alert')).toHaveTextContent('The passwords do not match.')
    expect(api.post).not.toHaveBeenCalled()
  })

  it('resets the password and clears any existing session', async () => {
    sessionStorage.setItem('tally_token', 'old-session')
    api.get.mockRejectedValue(apiError(401, 'unauthorized', 'Session expired'))
    api.post.mockResolvedValue({ data: { ok: true, message: 'Your password has been reset. Please sign in with your new password.' } })
    renderWithProviders(<ResetPassword />, { route: '/reset-password?token=abc123def456' })
    await userEvent.type(screen.getByLabelText('New password'), 'newpass456')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'newpass456')
    await userEvent.click(screen.getByRole('button', { name: /update password/i }))
    expect(api.post).toHaveBeenCalledWith('/auth/reset-password', { token: 'abc123def456', new_password: 'newpass456' })
    expect(await screen.findByText('Password updated')).toBeInTheDocument()
    expect(sessionStorage.getItem('tally_token')).toBeNull()
  })

  it('offers a new link when the token has expired', async () => {
    api.post.mockRejectedValue(apiError(400, 'invalid_token', 'This link is invalid or has expired. Please request a new one.'))
    renderWithProviders(<ResetPassword />, { route: '/reset-password?token=expired-token-1' })
    await userEvent.type(screen.getByLabelText('New password'), 'newpass456')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'newpass456')
    await userEvent.click(screen.getByRole('button', { name: /update password/i }))
    expect(await screen.findByRole('link', { name: 'Request a new link' })).toHaveAttribute('href', '/forgot-password')
  })
})

describe('VerifyEmail', () => {
  it('verifies exactly once, even under StrictMode double effects (tokens are single-use)', async () => {
    api.post.mockResolvedValue({ data: { ok: true, message: 'Your email address is verified.' } })
    renderWithProviders(<StrictMode><VerifyEmail /></StrictMode>, { route: '/verify-email?token=verify-token-1' })
    expect(await screen.findByText("You're verified!")).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post).toHaveBeenCalledWith('/auth/verify-email', { token: 'verify-token-1' })
  })

  it('shows why verification failed', async () => {
    api.post.mockRejectedValue(apiError(400, 'invalid_token', 'This link is invalid or has expired. Please request a new one.'))
    renderWithProviders(<VerifyEmail />, { route: '/verify-email?token=used-token-1' })
    expect(await screen.findByText("Couldn't verify")).toBeInTheDocument()
    expect(screen.getByText(/invalid or has expired/)).toBeInTheDocument()
  })
})
