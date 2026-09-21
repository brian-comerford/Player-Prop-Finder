import { useEffect, useState } from "react";

export type ThemeChoice = "system" | "light" | "dark";

const STORAGE_KEY = "theme";

function readStoredTheme(): ThemeChoice {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    // localStorage can throw in private-browsing/blocked-storage contexts --
    // just fall back to following the system setting.
  }
  return "system";
}

function prefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme(theme: ThemeChoice) {
  const isDark = theme === "dark" || (theme === "system" && prefersDark());
  document.documentElement.classList.toggle("dark", isDark);
}

/**
 * Manual light/dark/system override, backed by localStorage. Defaults to
 * "system" so the site follows the device's own setting until someone
 * explicitly overrides it -- see index.html for the inline script that
 * applies the stored choice before React mounts, to avoid a flash of the
 * wrong theme on load.
 */
export function useTheme() {
  const [theme, setTheme] = useState<ThemeChoice>(readStoredTheme);

  useEffect(() => {
    applyTheme(theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // ignore -- the choice just won't persist across reloads
    }
  }, [theme]);

  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => applyTheme("system");
    mq.addEventListener("change", handleChange);
    return () => mq.removeEventListener("change", handleChange);
  }, [theme]);

  return { theme, setTheme };
}
