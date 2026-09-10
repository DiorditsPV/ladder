import { memo } from "react";
import { hexA, lighten } from "../types";
import type { Band } from "../layout";

// Ruling C2: счётчик разобранных/оценённых по ряду — добавляется к Band в BoardPage
// (layout.ts не знает о прогрессе, поэтому здесь расширение, а не правка Band).
export type BandWithCount = Band & { done: number; count: number };

export interface BandsNodeData {
  bands: BandWithCount[];
  width: number;
  labelW: number;
  dark: boolean;
  height: number;
  [key: string]: unknown;
}

// Левая ось сложности (junior→senior сверху вниз). Горизонтальные разделители полос
// вынесены в GuidesNode (переключаемые направляющие).
function BandsNodeImpl({ data }: { data: BandsNodeData }) {
  const { bands, width, labelW, height, dark } = data;
  return (
    <div className="bands" style={{ width: labelW + width, height }}>
      {bands.map((b) => {
        const color = b.color;
        return (
          <div
            key={b.difficulty}
            className="bands__label"
            // На тёмном фоне «сырой» цвет уровня почти не читается — осветляем подпись.
            style={{
              top: b.y,
              height: b.height,
              width: labelW,
              color: dark ? lighten(color, 0.5) : color,
              background: hexA(color, dark ? 0.12 : 0.1),
            }}
          >
            <span>{b.label}</span>
            <span className="bands__count">{b.done}/{b.count}</span>
          </div>
        );
      })}
    </div>
  );
}

export const BandsNode = memo(BandsNodeImpl);
