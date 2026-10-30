"use client";

import { useEffect, useState } from "react";

// Same key as the no-flash script in app/layout.js.
const THEME_KEY = "civicfix_theme";

export default function ThemeToggle() {
  const [theme, setTheme] = useState(null); // null = server render / not yet mounted

  useEffect(() => {
    setTheme(document.documentElement.dataset.theme || "dark");
  }, []);

  const toggle = () => {
    const current = document.documentElement.dataset.theme || "dark";
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    setTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* private mode - theme just won't persist */
    }
  };

  // "◐" placeholder avoids a hydration mismatch before the stored theme is read.
  if (theme === null) {
    return (
      <button className="btn small ghost" aria-label="Toggle theme" disabled>
        ◐
      </button>
    );
  }

  return (
    <button
      className="btn small ghost"
      onClick={toggle}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
    >
      {theme === "dark" ? "☀️ Light" : "🌙 Dark"}
    </button>
  );
}
