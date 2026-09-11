import { useCallback, useEffect, useState } from "react";
import { api, type AuthUser } from "./api";
import { Login } from "./components/Login";
import BoardPage from "./pages/BoardPage";
import { BankPage } from "./pages/BankPage";
import { HomePage } from "./pages/HomePage";
import { Landing } from "./pages/Landing";
import { PeoplePage } from "./pages/PeoplePage";
import { pairOf, poolsForLang } from "./poolLang";
import { href, useRoute, type Route } from "./router";
import { useSession } from "./session";
import { useLang, useT } from "./i18n";
import type { PoolConfig } from "./types";

// Раздаёт страницы по маршруту; режим — из сессии (spec 2026-09-11): без входа — стартовый экран
// и демо (только демо-направления), после входа — полный режим. Список пулов грузится на вход и
// перезагружается при смене пользователя: он нужен и меню, и доске (таксономия колонок), и банку.
// Неизвестный (или недоступный режиму) пул в адресе → меню с пометкой.

// Куда увести с маршрута, недоступного режиму (null — остаться).
function redirectFor(route: Route, user: AuthUser | null): string | null {
  if (user) {
    if (route.name === "login" || route.name === "demo") return href.home;
    if (route.name === "people" && user.role !== "owner") return href.home;
    return null;
  }
  return route.name === "people" ? href.home : null;
}

export default function Router() {
  const t = useT();
  const [lang] = useLang();
  const route = useRoute();
  const { user, refresh } = useSession();
  const [pools, setPools] = useState<PoolConfig[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reloadPools = useCallback(() => api.pools().then(setPools).catch((e) => setError(String(e))), []);
  useEffect(() => {
    setPools(null);
    setError(null);
    void reloadPools();
  }, [reloadPools, user?.id]);

  const redirect = redirectFor(route, user);
  useEffect(() => {
    if (redirect) window.location.replace(redirect);
  }, [redirect]);
  // Язык контента: доска/банк направления уходят на его пару на языке интерфейса, если пара есть
  // (#/board/data-engineer ↔ #/board/data-engineer-en). Эффект — до ранних return (порядок хуков).
  useEffect(() => {
    if (!pools || (route.name !== "board" && route.name !== "bank")) return;
    const current = pools.find((p) => p.id === route.pool);
    const pair = current ? pairOf(pools, current, lang) : null;
    if (pair && current && pair.id !== current.id) {
      window.location.replace(route.name === "board" ? href.board(pair.id) : href.bank(pair.id));
    }
  }, [lang, pools, route]);
  if (redirect) return null;

  if (route.name === "login") {
    return <Login onLogin={async () => { await refresh(); window.location.replace(href.home); }} />;
  }
  if (!user && route.name === "home") return <Landing />;
  if (error) return <div className="loading">{t("Не удалось загрузить направления: {error}", { error })}</div>;
  if (!pools) return <div className="loading">{t("Загрузка…")}</div>;

  const demo = !user;
  // Главная показывает направления на языке интерфейса (перевод вместо оригинала, где он есть);
  // доска и банк ищут пул по полному списку — адрес может указывать и на перевод.
  const homePools = poolsForLang(pools, lang);
  const poolOf = (id: string) => pools.find((p) => p.id === id) ?? null;
  switch (route.name) {
    case "board": {
      const pool = poolOf(route.pool);
      if (!pool) return <HomePage pools={homePools} demo={demo} notice={t("Направления «{pool}» нет", { pool: route.pool })} onChanged={reloadPools} />;
      // key — чтобы смена пула пересоздавала доску целиком (состояние, таймеры).
      return <BoardPage key={pool.id} pool={pool} />;
    }
    case "bank": {
      const pool = poolOf(route.pool);
      if (!pool) return <HomePage pools={homePools} demo={demo} notice={t("Направления «{pool}» нет", { pool: route.pool })} onChanged={reloadPools} />;
      return <BankPage key={pool.id} pool={pool} onChanged={reloadPools} />;
    }
    case "people":
      // Только owner: остальных redirectFor уже увёл на главную.
      return <PeoplePage />;
    default:
      return <HomePage pools={homePools} demo={demo} onChanged={reloadPools} />;
  }
}
