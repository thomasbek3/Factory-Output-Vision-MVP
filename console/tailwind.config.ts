import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        "bg-rail": "var(--bg-rail)",
        panel: "var(--panel)",
        "panel-2": "var(--panel-2)",
        border: "var(--border)",
        "border-soft": "var(--border-soft)",
        text: "var(--text)",
        "text-mut": "var(--text-mut)",
        "text-dim": "var(--text-dim)",
        accent: "var(--accent)",
        "accent-hi": "var(--accent-hi)",
        "accent-tint": "var(--accent-tint)",
        good: "var(--good)",
        "good-tint": "var(--good-tint)",
        bad: "var(--bad)",
        "bad-tint": "var(--bad-tint)",
        warn: "var(--warn)",
        "warn-tint": "var(--warn-tint)",
        idle: "var(--idle)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "ui-sans-serif", "system-ui"],
      },
      borderRadius: {
        panel: "12px",
      },
      boxShadow: {
        panel:
          "0 10px 28px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.05)",
      },
    },
  },
  plugins: [],
};

export default config;
