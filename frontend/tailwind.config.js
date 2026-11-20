/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      keyframes: {
        shake: {
          '0%, 100%': { transform: 'translateX(0)' },
          '15%, 45%, 75%': { transform: 'translateX(-8px)' },
          '30%, 60%, 90%': { transform: 'translateX(8px)' },
        },
        slidein: {
          '0%': { opacity: '0', transform: 'translateY(-10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        glow: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(16,185,129,0.55)' },
          '50%': { boxShadow: '0 0 0 10px rgba(16,185,129,0)' },
        },
        alarm: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(220,38,38,0.6)' },
          '50%': { boxShadow: '0 0 0 14px rgba(220,38,38,0)' },
        },
      },
      animation: {
        shake: 'shake 0.7s ease-in-out 1',
        slidein: 'slidein 0.45s ease-out both',
        glow: 'glow 1.6s ease-in-out infinite',
        alarm: 'alarm 1.4s ease-in-out 3',
        reject: 'shake 0.7s ease-in-out 1, alarm 1.4s ease-in-out 3',
      },
    },
  },
  plugins: [],
}
