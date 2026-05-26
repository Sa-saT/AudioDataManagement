import type { Config } from 'tailwindcss'

export default <Partial<Config>>{
  content: [
    './app/**/*.{vue,js,ts}',
    './components/**/*.{vue,js,ts}',
    './pages/**/*.{vue,js,ts}',
    './layouts/**/*.{vue,js,ts}',
  ],
  theme: {
    extend: {
      colors: {
        // Brand / Accent
        primary: {
          DEFAULT: '#f54e00',
          active: '#d04200',
        },
        // Surface
        canvas: {
          DEFAULT: '#f7f7f4',
          soft: '#fafaf7',
        },
        surface: {
          card: '#ffffff',
          strong: '#e6e5e0',
        },
        // Hairlines
        hairline: {
          DEFAULT: '#e6e5e0',
          soft: '#efeee8',
          strong: '#cfcdc4',
        },
        // Text
        ink: '#26251e',
        body: {
          DEFAULT: '#5a5852',
          strong: '#26251e',
        },
        muted: {
          DEFAULT: '#807d72',
          soft: '#a09c92',
        },
        // Semantic
        success: '#1f8a65',
        error: '#cf2d56',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '"Helvetica Neue"', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      letterSpacing: {
        'display-mega': '-0.03em',
        'display-lg': '-0.02em',
        'display-md': '-0.0125em',
      },
      borderRadius: {
        xs: '4px',
        sm: '6px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
    },
  },
}
