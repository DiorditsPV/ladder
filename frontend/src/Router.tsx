import { useEffect, useState } from "react";
import { api } from "./api";
import BoardPage from "./pages/BoardPage";
import { BankPage } from "./pages/BankPage";
import { HomePage } from "./pages/HomePage";
import { useRoute } from "./router";
import { useT } from "./i18n";
import type { PoolConfig } from "./types";

// Раздаёт страницы по маршруту. Список пулов грузится один раз на вход: он нужен и меню,
// и доске (таксономия колонок), и банку. Неизвестный пул в адресе → меню с пометкой.
export default function Router() {
  const t = useT();
  const route = useRoute();
  const [pools, setPools] = useState<PoolConfig[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reloadPools = () => api.pools().then(setPools).catch((e) => setError(String(e)));
  useEffect(() => {
    reloadPools();
  }, []);

  if (error) return <div className="loading">{t("Не удалось загрузить направления: {error}", { error })}</div>;
  if (!pools) return <div className="loading">{t("Загрузка…")}</div>;

  const poolOf = (id: string) => pools.find((p) => p.id === id) ?? null;

  switch (route.name) {
    case "board": {
      const pool = poolOf(route.pool);
      if (!pool) return <HomePage pools={pools} notice={t("Направления «{pool}» нет", { pool: route.pool })} onChanged={reloadPools} />;
      // key — чтобы смена пула пересоздавала доску целиком (состояние, таймеры).
      return <BoardPage key={pool.id} pool={pool} />;
    }
    case "bank": {
      const pool = poolOf(route.pool);
      if (!pool) return <HomePage pools={pools} notice={t("Направления «{pool}» нет", { pool: route.pool })} onChanged={reloadPools} />;
      return <BankPage key={pool.id} pool={pool} onChanged={reloadPools} />;
    }
    default:
      return <HomePage pools={pools} onChanged={reloadPools} />;
  }
}
