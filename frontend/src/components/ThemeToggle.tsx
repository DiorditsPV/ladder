import { Moon, Sun } from "lucide-react";
import { useT } from "../i18n";
import { useTheme } from "../theme";

// Переключатель темы в шапке каждой страницы: иконка показывает, НА какую тему переключит.
// Класс .themebtn — на него ходит smoke.
export function ThemeToggle() {
  const t = useT();
  const { theme, toggleTheme } = useTheme();
  const dark = theme === "dark";
  const label = dark ? t("Светлая тема") : t("Тёмная тема");
  return (
    <button className="themebtn iconbtn btn--quiet" onClick={toggleTheme} aria-pressed={dark} aria-label={label} title={label}>
      {dark ? <Sun size={16} strokeWidth={1.75} aria-hidden="true" /> : <Moon size={16} strokeWidth={1.75} aria-hidden="true" />}
    </button>
  );
}
