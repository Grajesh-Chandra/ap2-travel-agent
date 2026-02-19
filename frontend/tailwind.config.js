/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'space-bg': '#030712',
        'panel': '#0d1117',
        'gold': '#c9a84c',
        'gold-dark': '#a68a3a',
        'success': '#22c55e',
        'info': '#38bdf8',
        'danger': '#ef4444',
        'border-light': 'rgba(255,255,255,0.08)',
        'border-medium': 'rgba(255,255,255,0.15)',
      },
      fontFamily: {
        'heading': ['"Space Grotesk"', 'sans-serif'],
        'body': ['"DM Sans"', 'sans-serif'],
        'mono': ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
