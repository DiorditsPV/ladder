import { useState } from "react";
import type { LevelDraft } from "../api";
import { useT } from "../i18n";
import { newUid } from "./BlocksEditor";

// Уровни сложности направления — ряды матрицы сверху вниз: первый в списке самый лёгкий (верхний ряд).
// Простой список без drag & drop: порядок — стрелками ↑ ↓, как в меню раздела BlocksEditor.
// Классы свои (levels__*), не struct__*: smoke ищет поля разделов по .struct__name, уровни в них попадать не должны.
export const LEVELS_MIN = 2;
export const LEVELS_MAX = 8;

export const emptyLevel = (): LevelDraft => ({ uid: newUid(), label: "" });

/** 2–8 уровней с непустыми названиями — иначе сервер ответит 422 (pools.parse_levels). */
export const levelsValid = (levels: LevelDraft[]): boolean =>
  levels.length >= LEVELS_MIN && levels.length <= LEVELS_MAX && levels.every((l) => l.label.trim() !== "");

const uidOf = (l: LevelDraft, i: number): string => l.uid ?? l.id ?? `l${i}`;

// nodeCounts (по id уровня) — confirm перед удалением уровня с вопросами: сервер удалит их вместе с ним.
export function LevelsEditor({ levels, onChange, nodeCounts }: {
  levels: LevelDraft[];
  onChange: (l: LevelDraft[]) => void;
  nodeCounts?: Record<string, number>;
}) {
  const t = useT();
  const [focusKey, setFocusKey] = useState<string | null>(null);

  const patch = (i: number, label: string) => onChange(levels.map((l, j) => (j === i ? { ...l, label } : l)));
  const move = (from: number, to: number) => {
    if (from === to || to < 0 || to >= levels.length) return;
    const next = [...levels];
    const [l] = next.splice(from, 1);
    next.splice(to, 0, l);
    onChange(next);
  };
  const remove = (i: number) => {
    const l = levels[i];
    const n = l.id ? (nodeCounts?.[l.id] ?? 0) : 0;
    if (n > 0 && !window.confirm(t("Удалить уровень «{label}» и его вопросы ({n})?", { label: l.label, n }))) return;
    onChange(levels.filter((_, j) => j !== i));
  };
  const add = () => {
    if (levels.length >= LEVELS_MAX) return;
    const l = emptyLevel();
    setFocusKey(uidOf(l, levels.length));
    onChange([...levels, l]);
  };

  return (
    <div className="levels">
      {levels.map((l, i) => {
        const uid = uidOf(l, i);
        return (
          <div key={uid} className="levels__row">
            <span className="levels__n" aria-hidden="true">{i + 1}</span>
            <input
              className="levels__name"
              placeholder={t("Название уровня")}
              aria-label={t("Название уровня")}
              value={l.label}
              autoFocus={focusKey === uid}
              onChange={(e) => patch(i, e.target.value)}
              onKeyDown={(e) => {
                // Enter в последнем уровне — сразу следующий: список набивается без мыши.
                if (e.key === "Enter" && i === levels.length - 1 && l.label.trim()) {
                  e.preventDefault();
                  add();
                }
              }}
            />
            <button type="button" className="levels__btn" title={t("Вверх")} aria-label={t("Вверх")} disabled={i === 0} onClick={() => move(i, i - 1)}>↑</button>
            <button type="button" className="levels__btn" title={t("Вниз")} aria-label={t("Вниз")} disabled={i === levels.length - 1} onClick={() => move(i, i + 1)}>↓</button>
            {/* Пока число вопросов не загружено, удалять уровень с id нельзя — иначе confirm не спросится. */}
            <button
              type="button"
              className="levels__del"
              title={t("Убрать уровень")}
              aria-label={t("Убрать уровень")}
              disabled={levels.length <= LEVELS_MIN || (!!l.id && !nodeCounts)}
              onClick={() => remove(i)}
            >
              ×
            </button>
          </div>
        );
      })}
      <button type="button" className="levels__add" onClick={add} disabled={levels.length >= LEVELS_MAX}>
        {t("+ Добавить уровень")}
      </button>
    </div>
  );
}
