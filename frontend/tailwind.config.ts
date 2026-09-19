import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#000000',
        foreground: '#ecebe7',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
        display: ['Inter', 'Plus Jakarta Sans', 'Google Sans', 'sans-serif'],
      },
      animation: {
        'star-btn': 'star-btn calc(var(--duration, 3) * 1s) linear infinite',
        marquee: 'marquee 40s linear infinite',
        shimmer: 'shimmer 6s linear infinite',
        'pulse-mark': 'pulse-mark 3.2s ease-in-out infinite',
      },
      keyframes: {
        'star-btn': {
          '0%': { offsetDistance: '0%' },
          '100%': { offsetDistance: '100%' },
        },
        marquee: {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        },
        shimmer: {
          to: { backgroundPosition: '-220% 0' },
        },
        'pulse-mark': {
          '0%, 100%': { opacity: '0.55', boxShadow: '0 0 6px rgba(255, 255, 255, 0.25)' },
          '50%': { opacity: '1', boxShadow: '0 0 18px rgba(255, 255, 255, 0.6)' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
