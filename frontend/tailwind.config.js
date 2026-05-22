/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        /* 브랜드 (CSS 변수 연결) */
        brand: {
          red:   'var(--brand-red)',
          gray:  'var(--brand-gray)',
          black: 'var(--brand-black)',
        },
        /* 시맨틱 토큰 — bg-surface, text-body 등으로 사용 */
        surface:     'var(--color-bg-surface)',
        'surface-alt': 'var(--color-bg-surface-alt)',
        page:        'var(--color-bg-page)',
        accent:      'var(--color-accent)',
        'accent-soft': 'var(--color-accent-soft)',
        success:     'var(--color-success)',
        warning:     'var(--color-warning)',
        danger:      'var(--color-danger)',
        info:        'var(--color-info)',
      },
      fontFamily: {
        sans: ['var(--font-primary)'],
        mono: ['var(--font-mono)'],
      },
      fontSize: {
        'token-xs':   'var(--font-size-xs)',
        'token-sm':   'var(--font-size-sm)',
        'token-base': 'var(--font-size-base)',
        'token-md':   'var(--font-size-md)',
        'token-lg':   'var(--font-size-lg)',
        'token-xl':   'var(--font-size-xl)',
        'token-2xl':  'var(--font-size-2xl)',
      },
      boxShadow: {
        'token-sm': 'var(--shadow-sm)',
        'token-md': 'var(--shadow-md)',
        'token-lg': 'var(--shadow-lg)',
      },
      borderRadius: {
        'token-card':    'var(--card-radius)',
        'token-card-sm': 'var(--card-radius-sm)',
        'token-modal':   'var(--modal-radius)',
        'token-badge':   'var(--badge-radius)',
        'token-btn':     'var(--btn-radius)',
      },
      spacing: {
        'token-xs': 'var(--gap-xs)',
        'token-sm': 'var(--gap-sm)',
        'token-md': 'var(--gap-md)',
        'token-lg': 'var(--gap-lg)',
        'token-xl': 'var(--gap-xl)',
      },
    },
  },
  plugins: [],
}
