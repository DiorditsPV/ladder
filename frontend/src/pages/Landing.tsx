import { ArrowRight } from "lucide-react";
import { LangSwitch } from "../components/LangSwitch";
import { ThemeToggle } from "../components/ThemeToggle";
import { useT } from "../i18n";
import { href } from "../router";

// Стартовый экран без входа: демо в приоритете, вход — приглушённая ссылка в углу (spec 2026-09-11).
export function Landing() {
  const t = useT();
  return (
    <div className="landing">
      <header className="landing__top">
        <ThemeToggle />
        <LangSwitch />
      </header>
      <main className="landing__main">
        <h1 className="landing__title">Ladder</h1>
        <p className="landing__pitch">
          {t("Тема разложена на колонки и ступени. Проходите карточки и отмечайте: знаю, повторить, не знаю.")}
        </p>
        <a className="landing__demo btn--primary" href={href.demo}>
          {t("Открыть демо")}
          <ArrowRight size={18} strokeWidth={1.75} aria-hidden="true" />
        </a>
        <p className="landing__note">{t("Дата-инженер и системный аналитик — на русском и английском.")}</p>
      </main>
      <a className="landing__login" href={href.login}>{t("Вход")}</a>
    </div>
  );
}
