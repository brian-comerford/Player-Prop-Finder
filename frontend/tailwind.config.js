/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  future: {
    // hover: styles only on devices that really hover, so a tap on a phone
    // doesn't leave a row or button stuck in its hover color.
    hoverOnlyWhenSupported: true,
  },
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
