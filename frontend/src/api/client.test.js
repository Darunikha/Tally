import { describe, expect, it } from 'vitest'
import { cleanParams, errorMessage, tokenStore } from './client'

const apiErr = (status, error) => ({ response: { status, data: { error } } })

describe('errorMessage', () => {
  it('returns the API error message', () => {
    expect(errorMessage(apiErr(409, { code: 'email_taken', message: 'An account with this email already exists' })))
      .toBe('An account with this email already exists')
  })
  it('lists field-level validation problems', () => {
    const err = apiErr(422, {
      code: 'validation_error', message: 'Invalid request',
      details: [{ field: 'password', message: 'too short' }, { field: '', message: 'bad body' }],
    })
    expect(errorMessage(err)).toBe('password: too short; bad body')
  })
  it('explains network failures and timeouts', () => {
    expect(errorMessage(new Error('Network Error'))).toBe('Cannot reach the server - is the API running?')
    expect(errorMessage({ code: 'ECONNABORTED' })).toBe('The request timed out')
  })
  it('falls back for unknown error bodies', () => {
    expect(errorMessage({ response: { status: 500, data: {} } }, 'Fallback')).toBe('Fallback')
  })
})

describe('cleanParams', () => {
  it('drops empty values but keeps zero and false', () => {
    expect(cleanParams({ a: '', b: null, c: undefined, d: 0, e: false, f: 'x' })).toEqual({ d: 0, e: false, f: 'x' })
    expect(cleanParams(undefined)).toEqual({})
  })
})

describe('tokenStore', () => {
  it('stores the session token in sessionStorage only', () => {
    tokenStore.set('abc')
    expect(tokenStore.get()).toBe('abc')
    expect(sessionStorage.getItem('tally_token')).toBe('abc')
    // Node 25+ shadows jsdom's localStorage with its own (unavailable) one, so only check where it exists
    if (globalThis.localStorage) expect(globalThis.localStorage.getItem('tally_token')).toBeNull()
    tokenStore.clear()
    expect(tokenStore.get()).toBeNull()
  })
})
