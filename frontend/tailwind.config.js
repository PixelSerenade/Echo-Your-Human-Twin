/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // App Theme Surfaces (backed by CSS variables)
        app: {
          DEFAULT: 'var(--bg-app)',
          light: '#FAF7FF',
          dark: '#120F1C',
        },
        surface: {
          DEFAULT: 'var(--surface-card)',
          subtle: 'var(--surface-subtle)',
          light: '#FFFFFF',
          dark: '#1D1830',
          subtleLight: '#F4EEFF',
          subtleDark: '#26203D',
        },
        content: {
          DEFAULT: 'var(--text-main)',
          muted: 'var(--text-muted)',
          mainLight: '#1B1530',
          mainDark: '#F4F0FF',
          mutedLight: '#6B6485',
          mutedDark: '#A9A1C4',
        },
        stroke: {
          DEFAULT: 'var(--border-subtle)',
          light: '#ECE6FA',
          dark: '#2E2747',
        },
        // Thinking Styles
        style: {
          rational: '#2EC4B6',      // Mint / Teal
          emotional: '#FF8FA3',     // Peach / Pink
          ambitiousFrom: '#8B5CF6', // Violet
          ambitiousTo: '#FF9F43',   // Orange
        },
        // Brand Gradients
        brand: {
          purple: '#7C5CFF',
          coral: '#FF7A9E',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        heading: ['"Plus Jakarta Sans"', 'Sora', 'sans-serif'],
      },
      borderRadius: {
        '2xl': '16px',
        '3xl': '24px',
      },
      boxShadow: {
        'soft-light': '0 8px 30px rgba(124, 92, 255, 0.08), 0 2px 6px rgba(0, 0, 0, 0.02)',
        'glow-purple': '0 0 24px rgba(124, 92, 255, 0.35)',
        'glow-rational': '0 0 20px rgba(46, 196, 182, 0.35)',
        'glow-emotional': '0 0 20px rgba(255, 143, 163, 0.35)',
        'glow-ambitious': '0 0 20px rgba(139, 92, 246, 0.35)',
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'orb-breathe': 'orbBreathe 5s ease-in-out infinite',
        'fade-in': 'fadeIn 0.25s ease-out forwards',
        'pop': 'pop 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards',
      },
      keyframes: {
        orbBreathe: {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.92' },
          '50%': { transform: 'scale(1.06)', opacity: '1' },
        },
        fadeIn: {
          'from': { opacity: '0', transform: 'translateY(6px)' },
          'to': { opacity: '1', transform: 'translateY(0)' },
        },
        pop: {
          '0%': { transform: 'scale(0.95)' },
          '70%': { transform: 'scale(1.03)' },
          '100%': { transform: 'scale(1)' },
        }
      }
    },
  },
  plugins: [],
}
