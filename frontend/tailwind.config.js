/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#effaf7",
          100: "#d6f3eb",
          500: "#0f766e",
          700: "#115e59"
        }
      }
    }
  },
  plugins: [],
};
