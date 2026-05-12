/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        // Violet primary — matches Stitch "ShopIQ Intelligence System"
        brand: {
          50:  '#f5f0ff',
          100: '#ede5ff',
          200: '#dfd1ff',  // primary-container (Stitch)
          300: '#cdc0ed',  // primary-fixed-dim
          400: '#b8a8e0',
          500: '#9b88cc',
          600: '#635880',  // inverse-primary
          700: '#4b4166',
          800: '#342b4f',  // on-primary
          900: '#1f1538',
          950: '#120e24',
        },
        // Deep ink surfaces — zinc scale matches Stitch dark palette exactly
        // zinc-950 = #09090b (base), zinc-900 = #18181b (surface), zinc-800 = #27272a (border)
      },
      borderRadius: {
        DEFAULT: '0.25rem',  // 4px — Stitch ROUND_FOUR
      },
      keyframes: {
        'fade-in': { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        'pulse-slow': { '0%,100%': { opacity: '1' }, '50%': { opacity: '.5' } },
        'violet-glow': {
          '0%,100%': { boxShadow: '0 0 8px rgba(223,209,255,0.25)' },
          '50%':      { boxShadow: '0 0 20px rgba(223,209,255,0.5)' },
        },
      },
      animation: {
        'fade-in':     'fade-in 0.3s ease-out',
        'pulse-slow':  'pulse-slow 2s ease-in-out infinite',
        'violet-glow': 'violet-glow 2.5s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
