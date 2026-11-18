/** @type {import('tailwindcss').Config} */
const c = (name) => `rgb(var(--${name}) / <alpha-value>)` // defined per theme in src/index.css

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'] },
      colors: {
        canvas: c('canvas'),
        surface: c('surface'),
        sidebar: c('sidebar'),
        ink: { DEFAULT: c('ink'), soft: c('ink-soft'), muted: c('ink-muted'), faint: c('ink-faint') },
        line: c('line'),
        // 500-700 are text and tint colours and flip in dark mode; "solid" is for fills that carry white text
        brand: {
          50: c('brand-50'), 100: c('brand-100'), 200: c('brand-200'), 300: c('brand-300'), 400: c('brand-400'), 500: c('brand-500'),
          600: c('brand-600'), 700: c('brand-700'), 800: c('brand-800'), 900: c('brand-900'),
          solid: c('brand-solid'), 'solid-hover': c('brand-solid-hover'),
        },
        navy: { 50: c('navy-50'), 100: c('navy-100'), 500: c('navy-500'), 600: c('navy-600') },
        danger: { 50: c('danger-50'), 100: c('danger-100'), 500: c('danger-500'), 600: c('danger-600'), solid: c('danger-solid'), 'solid-hover': c('danger-solid-hover') },
        warn: { 50: c('warn-50'), 100: c('warn-100'), 500: c('warn-500') },
      },
      boxShadow: {
        card: '0 1px 2px rgba(20,33,61,0.04), 0 4px 16px -6px rgba(20,33,61,0.08)',
        pop: '0 12px 40px -12px rgba(20,33,61,0.25)',
      },
      borderRadius: { xl2: '1.125rem' },
    },
  },
  plugins: [],
}
