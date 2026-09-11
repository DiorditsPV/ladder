import type { Lang } from "./i18n";
import type { PoolConfig } from "./types";

// Язык контента: перевод заменяет оригинал на своём языке, если есть; иначе — оригинал (spec 2026-09-11).
export function poolsForLang(pools: PoolConfig[], lang: Lang): PoolConfig[] {
  const translations = new Map<string, PoolConfig>();
  for (const p of pools) if (p.translation_of && (p.lang ?? "ru") === lang) translations.set(p.translation_of, p);
  return pools
    .filter((p) => !p.translation_of)
    .map((p) => ((p.lang ?? "ru") === lang ? p : translations.get(p.id) ?? p));
}

/** Пара направления на языке lang (для переключателя на доске); null — пары нет. */
export function pairOf(pools: PoolConfig[], pool: PoolConfig, lang: Lang): PoolConfig | null {
  if ((pool.lang ?? "ru") === lang) return pool;
  if (pool.translation_of) {
    const original = pools.find((p) => p.id === pool.translation_of);
    if (original && (original.lang ?? "ru") === lang) return original;
  }
  return pools.find((p) => p.translation_of === pool.id && (p.lang ?? "ru") === lang) ?? null;
}
