// Типы соответствуют ответу бэкенда (FastAPI сериализует по alias → camelCase).

// Блок — строка: таксономию задаёт pool.yaml пула (см. PoolConfig), а не union-тип.
export type Block = string;
// Уровень — строка: список уровней и их порядок задаёт pool.levels (см. PoolConfig), а не union-тип.
export type Difficulty = string;
export type Kind = "question" | "task";

export interface QNode {
  id: string;
  kind: Kind;
  pool: string;
  block: Block;
  subblock?: string | null;
  topic: string;
  title?: string | null;
  difficulty: Difficulty;
  weight: number;
  question: string;
  answer: string;
  starterCode?: string | null;
  rubric: string[];
  tags: string[];
}

export interface ImportErr {
  file: string;
  error: string;
}

// Пул направления — зеркало content/<pool>/pool.yaml (GET /api/pools).
export interface SubblockCfg {
  id: string;
  label: string;
}
export interface BlockCfg {
  id: string;
  label: string;
  color: string; // семантический цвет блока (600-ряд)
  weight: number;
  subblocks: SubblockCfg[];
}
// Уровень сложности пула — зеркало pool.levels (порядок ascending: легче → сложнее).
export interface LevelCfg {
  id: string;
  label: string;
}
export interface PoolConfig {
  id: string;
  label: string;
  description: string;
  blocks: BlockCfg[];
  levels: LevelCfg[];
  counts?: { nodes: number };
  progress?: { known: number; review: number; unknown: number; total: number };
  // Демо-режим (spec 2026-09-11): видно без входа; язык контента; id оригинала, если это перевод.
  demo?: boolean;
  lang?: "ru" | "en";
  translation_of?: string | null;
}

// Статус чек-листа разбора (per-user): «знаю» / «повторить» / «не знаю».
export type Progress = "known" | "review" | "unknown";

const FALLBACK_COLOR = "#64748b";

export function blockOrder(pool: PoolConfig): string[] {
  return pool.blocks.map((b) => b.id);
}
export function blockLabel(pool: PoolConfig, block: string): string {
  return pool.blocks.find((b) => b.id === block)?.label ?? block;
}
export function blockColor(pool: PoolConfig, block: string): string {
  return pool.blocks.find((b) => b.id === block)?.color ?? FALLBACK_COLOR;
}
export function subLabel(pool: PoolConfig, block: string, sub: string): string {
  return pool.blocks.find((b) => b.id === block)?.subblocks.find((s) => s.id === sub)?.label ?? sub;
}

// Палитра уровней по индексу (снизу — легче, сверху — сложнее); первые четыре — прежние цвета
// base/junior/middle/senior, поэтому пулы на дефолтной четвёрке выглядят как раньше.
export const LEVEL_PALETTE = ["#1e40af", "#166534", "#854d0e", "#991b1b", "#6d28d9", "#0e7490", "#be185d", "#374151"];

export function levelOrder(pool: PoolConfig): string[] {
  return pool.levels.map((l) => l.id);
}
export function levelLabel(pool: PoolConfig, level: string): string {
  return pool.levels.find((l) => l.id === level)?.label ?? level;
}
export function levelColor(pool: PoolConfig, level: string): string {
  const i = pool.levels.findIndex((l) => l.id === level);
  return i >= 0 ? LEVEL_PALETTE[i % LEVEL_PALETTE.length] : FALLBACK_COLOR;
}

export interface GraphResponse {
  nodes: QNode[];
  errors: ImportErr[];
}

// Результат загрузки файла вопросов (POST /api/import).
export interface ImportAdded {
  id: string;
  block: Block;
  title: string;
  path: string;
}
export interface ImportResult {
  added: ImportAdded[];
  errors: ImportErr[];
}

// rgba из hex-цвета с заданной прозрачностью (для полупрозрачных дорожек).
// Осветлить цвет блока для тёмной темы: синий/фиолетовый на тёмном фоне иначе
// сливаются с подложкой, и заголовки колонок перестают читаться.
export function lighten(hex: string, amount: number): string {
  const h = hex.replace("#", "");
  const mix = (c: number) => Math.round(c + (255 - c) * amount);
  const r = mix(parseInt(h.slice(0, 2), 16));
  const g = mix(parseInt(h.slice(2, 4), 16));
  const b = mix(parseInt(h.slice(4, 6), 16));
  return `rgb(${r}, ${g}, ${b})`;
}

// Относительная яркость sRGB (WCAG 2.x); контраст с белым = 1.05 / (L + 0.05).
function relLuminance(r: number, g: number, b: number): number {
  const ch = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
}

/** Цвет плашки заголовка блока: затемняем цвет блока (от 0.15 шагом 0.05), пока белый текст
 *  не даст ≥ 4.5:1 (WCAG AA). Синему/фиолетовому хватает 0.15 (700-ряд), зелёному/янтарному
 *  нужно 0.2 — так плашка держит AA для любых цветов из pool.yaml. */
export function plateColor(hex: string): string {
  const h = hex.replace("#", "");
  const base = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  for (let amount = 0.15; amount <= 0.61; amount += 0.05) {
    const [r, g, b] = base.map((c) => Math.round(c * (1 - amount)));
    if (1.05 / (relLuminance(r, g, b) + 0.05) >= 4.5) return `rgb(${r}, ${g}, ${b})`;
  }
  return "#000";
}

export function hexA(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
