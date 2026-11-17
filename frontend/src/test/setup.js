import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
  sessionStorage.clear()
})

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
