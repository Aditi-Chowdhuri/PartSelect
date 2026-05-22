import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          blue:       '#0066CC',
          'blue-dark':'#004E9A',
          'blue-light':'#E8F1FA',
          orange:     '#e8651a',
          'orange-dark':'#c4521a',
          'orange-light':'#fff4ee',
        },
      },
      animation: {
        'fade-in':   'fadeIn 0.18s ease-out',
        'slide-up':  'slideUp 0.2s ease-out',
        'pulse-soft':'pulseSoft 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%':   { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.5' },
        },
      },
    },
  },
  plugins: [],
}

export default config
