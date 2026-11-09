/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B0D12", panel: "#131720", panel2: "#181d28", line: "#242b38", line2: "#2f3847",
        accent: "#4388FF", accent2: "#2f6fe0", ink: "#e6e9ef", mute: "#8a94a7", dim: "#5d6679",
        ok: "#3fb98a", warn: "#e0a43a", bad: "#e5584f",
      },
      fontFamily: { sans: ['"Inter Variable"', "Inter", "system-ui", "sans-serif"], mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] },
    },
  },
  plugins: [],
};
