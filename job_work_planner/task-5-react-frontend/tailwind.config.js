/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'industrial-charcoal': '#0F172A',
        'industrial-orange': '#F97316',
        'industrial-border': '#334155',
      },
      fontFamily: {
        'mono': ['"JetBrains Mono"', 'monospace'],
      }
    },
  },
  plugins: [],
}
