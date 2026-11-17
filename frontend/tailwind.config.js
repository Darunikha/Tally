/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'] },
      colors: {
        canvas: '#F6F6F1',
        surface: '#FFFFFF',
        ink: { DEFAULT: '#14213D', soft: '#3B4558', muted: '#6B7280', faint: '#9CA3AF' },
        line: '#E8E8E1',
        brand: { 50: '#EEF6F0', 100: '#DCEEE2', 200: '#B7DCC4', 300: '#8CC5A2', 400: '#5AA77B', 500: '#2F7D55', 600: '#266A47', 700: '#1E5439', 800: '#173F2B', 900: '#0F2A1D' },
        navy: { 500: '#3D5A80', 600: '#2E4566' },
        danger: { 50: '#FDF0EF', 100: '#FADBD8', 500: '#C2413B', 600: '#A3332E' },
        warn: { 50: '#FFF7E6', 100: '#FDEBC4', 500: '#B7791F' },
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
