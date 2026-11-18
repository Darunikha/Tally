import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
  sessionStorage.clear()
})

// Node 25+ shadows jsdom's localStorage with its own, unusable one; give tests a plain in-memory replacement
if (typeof globalThis.localStorage?.getItem !== 'function') {
  const data = new Map()
  const memory = {
    getItem: (k) => (data.has(String(k)) ? data.get(String(k)) : null),
    setItem: (k, v) => { data.set(String(k), String(v)) },
    removeItem: (k) => { data.delete(String(k)) },
    clear: () => data.clear(),
    key: (i) => [...data.keys()][i] ?? null,
    get length() { return data.size },
  }
  Object.defineProperty(globalThis, 'localStorage', { value: memory, configurable: true })
  Object.defineProperty(window, 'localStorage', { value: memory, configurable: true })
}

// jsdom has no matchMedia; tests run as a device that prefers light unless a test overrides it
window.matchMedia = window.matchMedia || ((query) => ({
  matches: false, media: query, onchange: null,
  addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false,
}))

// jsdom lacks these browser APIs that Recharts / the UI touch
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver || ResizeObserverStub
window.scrollTo = window.scrollTo || (() => {})
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {})
URL.createObjectURL = URL.createObjectURL || (() => 'blob:mock')
URL.revokeObjectURL = URL.revokeObjectURL || (() => {})
