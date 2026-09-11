import type { ReactNode } from "react";
import { LangSwitch } from "../components/LangSwitch";
import { ThemeToggle } from "../components/ThemeToggle";
import { useT } from "../i18n";
import { useHomeHref } from "../session";

// Каркас всех страниц, кроме доски: тонкая полоса «← Меню · заголовок [· действия · RU/EN]»,
// ниже — содержимое. Оформление (37 и альтернативы) приходит через те же токены.
export function PageShell({
  title,
  actions,
  children,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const t = useT();
  const homeHref = useHomeHref();
  return (
    <div className="page">
      <header className="pageshell">
        <a className="pageshell__back" href={homeHref}>{t("← Меню")}</a>
        <h1 className="pageshell__title">{title}</h1>
        <div className="pageshell__actions">
          {actions}
          <ThemeToggle />
          <LangSwitch />
        </div>
      </header>
      <main className="page__body">{children}</main>
    </div>
  );
}
