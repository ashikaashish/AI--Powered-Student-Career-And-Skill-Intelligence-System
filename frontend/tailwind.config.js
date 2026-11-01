/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Brand palette — matches the CareerAI Intelligence visual system.
        // "primary" is remapped from purple to brand blue/indigo so every
        // existing bg-primary-*/text-primary-* class across the app updates
        // automatically without touching each page's markup.
        primary: {
          50: '#f0f4fe',
          100: '#dde7fc',
          200: '#c2d5fa',
          300: '#99bcf7',
          400: '#699bf2',
          500: '#4378eb',
          600: '#2e5bdf',
          700: '#2346cb',
          800: '#213aa4',
          900: '#1e3482',
          950: '#142050',
        },
        brand: {
          50: '#f0f4fe',
          100: '#dde7fc',
          200: '#c2d5fa',
          300: '#99bcf7',
          400: '#699bf2',
          500: '#4378eb',
          600: '#2e5bdf',
          700: '#2346cb',
          800: '#213aa4',
          900: '#1e3482',
          950: '#142050',
        },
        sidebar: {
          bg: '#14203e',
          hover: '#1c2a4e',
          active: '#213563',
          text: '#a2b0d0',
          activeText: '#ffffff',
        },
        teal: {
          50: "#f0fdfa",
          500: "#0d9488",
          600: "#0f766e",
          700: "#0f5f57",
        },
        amber: {
          50: "#fffbeb",
          500: "#f59e0b",
          600: "#d97706",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 24, 40, 0.06), 0 1px 3px rgba(16, 24, 40, 0.08)",
      },
      borderRadius: {
        xl2: "1rem",
      },
    },
  },
  plugins: [],
}
