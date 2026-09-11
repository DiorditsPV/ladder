import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

// Цветовая тема — одна на всё приложение (стартовый экран, главная, доска, банк, «Люди»).
// По умолчанию светлая: системную тему не читаем. Выбор запоминается под своим ключом —
// старый ключ "theme" доска раньше записывала сама из системной настройки, это не выбор человека.
export type Theme = "light" | "dark";
const THEME_KEY = "ladder.theme";
const DESIGNS = ["37", "56", "57", "58"];

function readTheme(): Theme {
  try {
    return localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

/** Оформление доски (design-funnel): выставляется при загрузке, чтобы вид не менялся от захода на доску. */
export function readDesign(): string {
  try {
    const v = localStorage.getItem("design");
    return v && DESIGNS.includes(v) ? v : "37";
  } catch {
    return "37";
  }
}

/** Выставить тему и оформление до первой отрисовки — без вспышки другой темы. Зовётся в main.tsx. */
export function initTheme(): void {
  document.documentElement.dataset.theme = readTheme();
  document.documentElement.dataset.design = readDesign();
}

const Ctx = createContext<{ theme: Theme; toggleTheme: () => void }>({ theme: "light", toggleTheme: () => void 0 });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(readTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* приватный режим — тема живёт до перезагрузки */
    }
  }, [theme]);
  const toggleTheme = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  const value = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme(): { theme: Theme; toggleTheme: () => void } {
  return useContext(Ctx);
}
