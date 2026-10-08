/** Palette: cool mist surfaces, deep ink, petrol (circuit-board teal) for brand, one signal amber reserved for the primary action. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        mist: { 50: "#F7F9F9", 100: "#EEF2F3", 200: "#E1E8EA", 300: "#CBD6D9", 400: "#AEBDC1" },
        ink: { DEFAULT: "#0D1B1E", 700: "#2A3C40", 500: "#566A6F", 400: "#73868B" },
        petrol: { 50: "#E8F3F3", 100: "#CFE6E7", 200: "#A3CFD1", 500: "#14797F", 600: "#0E5257", 700: "#0A3F43", 900: "#06292C" },
        signal: { DEFAULT: "#F5B83D", 600: "#D99A12", 100: "#FDF1D4" },
        copper: { DEFAULT: "#B9692E", 100: "#F6E6D8" },
        alert: { DEFAULT: "#B93A27", 100: "#FADED9" },
        ok: { DEFAULT: "#2B7A4B", 100: "#DCF0E3" },
      },
      fontFamily: {
        display: ['"Bricolage Grotesque Variable"', "system-ui", "sans-serif"],
        sans: ['"Instrument Sans Variable"', "system-ui", "sans-serif"],
      },
      borderRadius: { hero: "1.75rem" },
      keyframes: {
        rise: { from: { opacity: 0, transform: "translateY(8px)" }, to: { opacity: 1, transform: "none" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
        pop: { "0%": { transform: "scale(.96)", opacity: 0 }, "100%": { transform: "scale(1)", opacity: 1 } },
      },
      animation: { rise: "rise .45s ease-out both", pop: "pop .25s ease-out both" },
    },
  },
  plugins: [],
};
