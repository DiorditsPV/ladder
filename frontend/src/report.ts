// Генерация самодостаточного HTML-экспорта банка вопросов направления.
// Открывается в браузере, печатается в PDF. Светлый (документ для шаринга/печати).

import { subOf } from "./layout";
import { getLang, nWord, t } from "./i18n";
import { blockColor, blockLabel, blockOrder, subLabel, levelColor, levelLabel, levelOrder, type PoolConfig, type QNode } from "./types";

const esc = (s: string) =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!));

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

// ---- Экспорт всего банка вопросов (полные формулировки + ответы, без оценок) ----
export function buildBankHtml(nodes: QNode[], pool: PoolConfig): string {
  const now = new Date();
  const dateStr = `${pad(now.getDate())}.${pad(now.getMonth() + 1)}.${now.getFullYear()} ${pad(now.getHours())}:${pad(now.getMinutes())}`;

  const blocks: string[] = [...blockOrder(pool)];
  for (const n of nodes) if (!blocks.includes(n.block)) blocks.push(n.block);

  const drank = (d: string) => levelOrder(pool).indexOf(d);

  const summaryChips = blocks
    .map((b) => ({ b, total: nodes.filter((n) => n.block === b).length }))
    .filter((s) => s.total > 0)
    .map(
      (s) =>
        `<div class="bchip" style="border-left-color:${blockColor(pool, s.b)}">
      <div class="bchip__name">${esc(blockLabel(pool, s.b))}</div>
      <div class="bchip__val">${s.total}</div>
    </div>`,
    )
    .join("");

  const sections = blocks
    .map((b) => {
      const list = nodes
        .filter((n) => n.block === b)
        .sort(
          (a, c) =>
            subOf(a).localeCompare(subOf(c)) ||
            drank(a.difficulty) - drank(c.difficulty) ||
            a.id.localeCompare(c.id),
        );
      if (!list.length) return "";
      const cards = list
        .map((n) => {
          const sub = n.subblock ? `<span class="sub">${esc(subLabel(pool, n.block, n.subblock))}</span> ` : "";
          const kind = n.kind === "task" ? `<span class="kind">${t("задача")}</span>` : "";
          const tags = n.tags.length
            ? `<div class="tags">${n.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>`
            : "";
          const starter = n.starterCode
            ? `<div class="lbl">${t("Заготовка кода")}</div><pre class="code">${esc(n.starterCode)}</pre>`
            : "";
          const rubric =
            n.rubric && n.rubric.length
              ? `<div class="lbl">${t("Критерии")}</div><ul class="rubric">${n.rubric.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>`
              : "";
          return `<article class="card">
  <div class="card__head">
    <span class="diff" style="color:${levelColor(pool, n.difficulty)}">${esc(levelLabel(pool, n.difficulty))}</span>
    ${sub}${kind}
  </div>
  <div class="qt">${esc(n.title || n.question)}</div>
  <div class="topic">${esc(n.topic)}</div>
  <div class="lbl">${t("Вопрос")}</div><div class="text">${esc(n.question)}</div>
  ${n.answer ? `<div class="lbl">${t("Ответ")}</div><div class="text">${esc(n.answer)}</div>` : ""}
  ${starter}${rubric}${tags}
</article>`;
        })
        .join("\n");
      return `<section>
  <h2 style="border-left-color:${blockColor(pool, b)}">${esc(blockLabel(pool, b))} <span class="cnt">${list.length}</span></h2>
  ${cards}
</section>`;
    })
    .join("\n");

  const body = nodes.length === 0 ? `<div class="empty">${t("Банк пуст.")}</div>` : sections;

  return `<!doctype html>
<html lang="${getLang()}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${t("Банк вопросов · Ladder")}</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1f2937; background: #f1f5f9; margin: 0; padding: 24px; }
  .sheet { max-width: 920px; margin: 0 auto; background: #fff; border-radius: 14px; box-shadow: 0 2px 12px rgba(0,0,0,.1); overflow: hidden; }
  .head { background: #0f172a; color: #fff; padding: 22px 30px; }
  .head h1 { margin: 0 0 6px; font-size: 21px; }
  .head .sub { opacity: .82; font-size: 13px; }
  .summary { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; padding: 16px 30px; border-bottom: 1px solid #e5e7eb; }
  .bchip { border-left: 4px solid; background: #f8fafc; border-radius: 8px; padding: 6px 12px; }
  .bchip__name { font-size: 11px; color: #6b7280; }
  .bchip__val { font-size: 17px; font-weight: 700; }
  section { padding: 6px 30px 8px; }
  h2 { font-size: 15px; border-left: 4px solid #999; padding-left: 10px; margin: 18px 0 10px; }
  h2 .cnt { font-size: 12px; font-weight: 500; color: #9ca3af; }
  .card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px 14px; margin: 0 0 10px; break-inside: avoid; }
  .card__head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
  .diff { font-size: 11px; text-transform: uppercase; font-weight: 700; }
  .sub { font-size: 11px; color: #6b7280; background: #f1f5f9; padding: 1px 6px; border-radius: 4px; }
  .kind { font-size: 10px; color: #92400e; background: #fef3c7; padding: 1px 6px; border-radius: 4px; }
  .qt { font-weight: 700; font-size: 14px; }
  .topic { font-size: 11px; color: #9ca3af; margin: 2px 0 6px; }
  .lbl { font-size: 10px; text-transform: uppercase; letter-spacing: .04em; color: #9ca3af; margin: 8px 0 2px; }
  .text { font-size: 13px; line-height: 1.5; white-space: pre-wrap; }
  .code { background: #0d1117; color: #e6edf3; padding: 10px; border-radius: 8px; overflow-x: auto; font-size: 12px; white-space: pre-wrap; }
  .rubric { margin: 2px 0 0; padding-left: 18px; font-size: 13px; line-height: 1.5; }
  .tags { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 3px; }
  .tag { font-size: 9px; color: #4338ca; background: #eef2ff; padding: 1px 5px; border-radius: 4px; }
  .empty { padding: 40px 30px; text-align: center; color: #9ca3af; }
  .foot { padding: 14px 30px 22px; font-size: 11px; color: #9ca3af; }
  @media print { body { background: #fff; padding: 0; } .sheet { box-shadow: none; border-radius: 0; } .card { break-inside: avoid; } }
</style></head>
<body>
  <div class="sheet">
    <div class="head">
      <h1>${t("Банк вопросов")}</h1>
      <div class="sub">${nodes.length} ${nWord(nodes.length, ["вопрос", "вопроса", "вопросов"], ["question", "questions"])} · ${dateStr}</div>
    </div>
    <div class="summary">${summaryChips}</div>
    ${body}
    <div class="foot">${t("Сгенерировано локальным сервисом «Ladder»")} · ${dateStr}</div>
  </div>
</body></html>`;
}

export function downloadBank(nodes: QNode[], pool: PoolConfig): void {
  const html = buildBankHtml(nodes, pool);
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const now = new Date();
  const stamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  const a = document.createElement("a");
  a.href = url;
  a.download = `ladder_bank_${stamp}.html`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
