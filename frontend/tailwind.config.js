/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        edge: {
          pos: "#22c55e",
          neg: "#ef4444",
        },
      },
    },
  },
  plugins: [],
};
