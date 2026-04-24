/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Noto Sans"', '"Noto Sans Arabic"', 'system-ui', 'sans-serif'],
        mono: ['"Noto Sans Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        paper:   'oklch(0.985 0.004 85)',
        card:    '#ffffff',
        hair:    'oklch(0.92 0.006 85)',
        line:    'oklch(0.88 0.008 85)',
        muted:   'oklch(0.55 0.01 240)',
        ink:     'oklch(0.22 0.01 240)',
        subtle:  'oklch(0.97 0.004 85)',
        primary:       'oklch(0.48 0.07 200)',
        'primary-2':   'oklch(0.42 0.08 200)',
        'primary-soft':'oklch(0.95 0.02 200)',
        amber:        'oklch(0.72 0.14 75)',
        'amber-soft': 'oklch(0.96 0.04 80)',
        red:          'oklch(0.55 0.16 25)',
        'red-soft':   'oklch(0.97 0.02 25)',
        green:        'oklch(0.55 0.11 155)',
        'green-soft': 'oklch(0.96 0.03 155)',
      },
      boxShadow: {
        elevated: '0 1px 2px rgba(20,30,40,0.04), 0 12px 32px -8px rgba(20,30,40,0.14)',
      },
      borderRadius: {
        kin: '6px',
        'kin-lg': '8px',
      },
    },
  },
  plugins: [],
};
