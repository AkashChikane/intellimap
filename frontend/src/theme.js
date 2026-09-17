import { createContext, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "intellimap-color-mode";
const ThemeContext = createContext({
  mode: "light",
  setMode: () => {},
  toggle: () => {},
});

function readStoredMode() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

function applyMode(mode) {
  const next = mode === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  document.documentElement.style.colorScheme = next;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", next === "dark" ? "#1F2F57" : "#FDFAF9");
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    /* ignore quota / private mode */
  }
}

export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState(readStoredMode);

  useEffect(() => {
    applyMode(mode);
  }, [mode]);

  const value = useMemo(
    () => ({
      mode,
      setMode: (next) => setModeState(next === "dark" ? "dark" : "light"),
      toggle: () => setModeState((current) => (current === "dark" ? "light" : "dark")),
    }),
    [mode]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
