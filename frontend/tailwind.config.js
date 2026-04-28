/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        brand: {
          50:  '#eef5ff',
          100: '#d9e8ff',
          200: '#bcd4ff',
          400: '#6fa8ff',
          600: '#2563eb',
          800: '#1e3a8a',
          900: '#172554',
        },
      },
      keyframes: {
        'fade-in': { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        'pulse-slow': { '0%,100%': { opacity: '1' }, '50%': { opacity: '.5' } },
      },
      animation: {
        'fade-in': 'fade-in 0.3s ease-out',
        'pulse-slow': 'pulse-slow 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
