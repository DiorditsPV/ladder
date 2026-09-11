// Набор витринных скриншотов для README: сеет статусы чек-листа через API и снимает экраны
// в docs/screenshots. Интерфейс переключается в английский (localStorage lang=en), поэтому
// сервер поднимают на англоязычном демо-контенте demo/content-en — тогда и вопросы в кадре
// на английском.
//
// Требует запущенного сервера и собранного фронта (frontend/dist). Терминал 1:
//   cd backend && INTERVIEW_CONTENT_DIR=$PWD/../demo/content-en \
//     INTERVIEW_DB_PATH=/tmp/ladder-shots.db INTERVIEW_OWNER_PASSWORD=interview-dev \
//     .venv/bin/uvicorn app.main:app --port 8004
// Терминал 2:
//   cd frontend && SHOTS_URL=http://localhost:8004 npm run shots
//
// Сид пишет статусы разбора в ту же БД, что отдаёт сервер, — снимай на отдельной.
// Не гейт: в проверку изменений (interview-verify) не входит.
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const BASE = process.env.SHOTS_URL || "http://localhost:8000";
const OUTDIR = process.env.SHOTS_DIR || path.resolve("../docs/screenshots");
const POOL = process.env.SHOTS_POOL || "data-engineer";
const VIEW = { width: 1600, height: 1000 };

// ---------- сид демо-данных ----------

const OWNER_EMAIL = process.env.SHOTS_OWNER_EMAIL || "owner@interview.local";
const OWNER_PASSWORD = process.env.SHOTS_OWNER_PASSWORD || "interview-dev";

// API за auth-гейтом: логинимся owner'ом и таскаем session-cookie руками
// (fetch в Node не хранит cookie-jar между вызовами).
let cookie = null;

const api = async (method, url, body) => {
  const r = await fetch(BASE + url, {
    method,
    headers: {
      ...(body ? { "content-type": "application/json" } : {}),
      ...(cookie ? { cookie } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${method} ${url} → ${r.status} ${await r.text()}`);
  const setCookie = r.headers.getSetCookie?.()[0];
  if (setCookie) cookie = setCookie.split(";")[0];
  return r.json();
};

const login = () => api("POST", "/api/auth/login", { email: OWNER_EMAIL, password: OWNER_PASSWORD });

// Детерминированный «профиль разбора»: какие карточки разобраны — функция от id ноды, поэтому
// повторный прогон даёт тот же кадр (диффы скриншотов не шумят).
const h = (s) => {
  let x = 0;
  for (const ch of s) x = (x * 31 + ch.charCodeAt(0)) % 1000;
  return x;
};

// Ровно coverage-доля карточек пула получает статус, остальные остаются неразобранными.
// Доля берётся внутри каждой колонки (иначе слабый h() оставляет колонку целиком неразобранной,
// и доска в кадре выглядит перекошенной), порядок — по h(id) с добором по id, статусы — по
// позиции: 3:1:1 known : review : unknown. Не вероятностно: доля и соотношение точные.
const plan = (nodes, coverage) => {
  const byBlock = new Map();
  for (const n of nodes) (byBlock.get(n.block) ?? byBlock.set(n.block, []).get(n.block)).push(n.id);
  const ids = [];
  for (const block of [...byBlock.keys()].sort()) {
    const inBlock = byBlock.get(block).sort((a, b) => h(a) - h(b) || (a < b ? -1 : 1));
    ids.push(...inBlock.slice(0, Math.round(inBlock.length * coverage)));
  }
  const CYCLE = ["known", "known", "known", "review", "unknown"];
  return new Map(ids.map((id, i) => [id, CYCLE[i % CYCLE.length]]));
};

async function seedPool(poolId, coverage) {
  const { nodes } = await api("GET", `/api/graph?pool=${poolId}`);
  if (!nodes.length) throw new Error(`пул ${poolId} пуст — поднимите сервер на demo/content-en`);
  const want = plan(nodes, coverage);
  // Идемпотентность на непустой БД: снимаем всё, чего нет в плане, и доставляем расхождения.
  const have = await api("GET", `/api/progress?pool=${poolId}`);
  for (const id of Object.keys(have)) if (!want.has(id)) await api("DELETE", `/api/progress/${id}`);
  for (const [id, status] of want) if (have[id] !== status) await api("PUT", `/api/progress/${id}`, { status });

  const byBlock = {};
  for (const n of nodes) {
    const b = (byBlock[n.block] ??= { total: 0, done: 0 });
    b.total += 1;
    if (want.has(n.id)) b.done += 1;
  }
  const breakdown = Object.entries(byBlock)
    .map(([b, v]) => `${b} ${v.done}/${v.total}`)
    .join(", ");
  console.log(`  seeded ${poolId}: ${want.size}/${nodes.length} (${breakdown})`);
  return nodes;
}

async function seed() {
  await login();
  const pools = await api("GET", "/api/pools");
  // Главный пул съёмки разобран на 60%, соседние — слабее: на главной видно разные полоски.
  for (const p of pools) await seedPool(p.id, p.id === POOL ? 0.6 : 0.35);
  return pools;
}

// ---------- съёмка ----------

const shot = async (page, name, opts = {}) => {
  const file = path.join(OUTDIR, name);
  await page.screenshot({ path: file, ...opts });
  console.log("  ✓", name);
};

const settle = (page, ms = 600) => page.waitForTimeout(ms);

/** Развернуть доску так, чтобы колонки не уходили под панель фильтров справа. */
async function frameBoard(page, { zoomOut = 1, panLeft = 170 } = {}) {
  await page.click(".react-flow__controls-fitview");
  await settle(page, 500);
  const box = await page.locator(".react-flow__pane").boundingBox();
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  for (let i = 0; i < zoomOut; i++) {
    await page.mouse.move(cx, cy);
    await page.mouse.wheel(0, 240);
    await settle(page, 250);
  }
  if (panLeft) {
    await page.mouse.move(cx, cy);
    await page.mouse.down();
    await page.mouse.move(cx - panLeft, cy, { steps: 12 });
    await page.mouse.up();
  }
  await settle(page, 400);
}

/** Приблизить канву к точке (карточки читаемы, видны точки статусов). */
async function zoomAt(page, box, steps = 3) {
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let i = 0; i < steps; i++) {
    await page.mouse.wheel(0, -240);
    await settle(page, 200);
  }
}

async function main() {
  await mkdir(OUTDIR, { recursive: true });
  await seed();

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: VIEW, deviceScaleFactor: 2 });
  const page = await ctx.newPage();

  // Доска за auth-гейтом: один раз логинимся в UI, дальше cookie живёт в контексте.
  // TODO(follow-up): после демо-режима (spec 2026-09-11) `/` без входа открывает стартовый экран,
  // а форма входа — по адресу `#/login` (goto(BASE + "/#/login")); ожидание .login__card сразу после
  // goto(BASE) ниже её не дождётся. Там же — перевод скриншотов на EN-пары (data-engineer-en).
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".login__card", { timeout: 10000 });
  await page.fill('.login__input[type="email"]', OWNER_EMAIL);
  await page.fill('.login__input[type="password"]', OWNER_PASSWORD);
  await page.click(".login__card button[type=submit]");
  await page.waitForSelector(".poolcard", { timeout: 15000 });
  // Английский интерфейс: скриншоты идут в англоязычный README. Язык читается на старте
  // приложения, поэтому после записи в localStorage нужна перезагрузка.
  await page.evaluate(() => localStorage.setItem("lang", "en"));
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForSelector(".poolcard", { timeout: 15000 });

  const prefs = (theme, filters) =>
    page.evaluate(
      ({ t, f }) => {
        localStorage.setItem("lang", "en");
        localStorage.setItem("ladder.theme", t);
        localStorage.setItem("bgVariant", "dots");
        localStorage.setItem("filtersOpen", f ? "1" : "0");
        localStorage.setItem("showTimer", "0"); // тикающий таймер ломает воспроизводимость кадра
      },
      { t: theme, f: filters },
    );

  /** Открыть доску пула с нужной темой и состоянием панели фильтров. */
  const openBoard = async ({ theme = "light", filters = false } = {}) => {
    await page.goto(BASE, { waitUntil: "domcontentloaded" });
    await prefs(theme, filters);
    await page.goto(`${BASE}/#/board/${POOL}`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".qnode", { timeout: 15000 });
    // Сид виден на доске: у части карточек есть точка статуса.
    await page.waitForSelector(".qnode__status[data-status]", { timeout: 15000 });
    await settle(page, 800);
  };

  // 01. Главная: направления как входы, число вопросов и полоска разбора.
  await page.goto(BASE + "/#/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".poolcard", { timeout: 10000 });
  await page.waitForSelector(".poolcard__progress", { timeout: 10000 });
  await settle(page, 400);
  await shot(page, "01-home.png");

  // 03. Доска: колонки × ступени, панель фильтров, тег гасит несовпавшие карточки.
  await openBoard({ filters: true });
  // Без панорамирования: fitView оставляет левую колонку в кадре, правую частично накрывает
  // панель фильтров — она и есть предмет кадра.
  await frameBoard(page, { zoomOut: 0, panLeft: 0 });
  await page.locator(".fp__tag", { hasText: "optimization" }).first().click();
  await settle(page, 500);
  const dimmed = await page.locator(".qnode--dimmed").count();
  if (dimmed < 1) throw new Error("фильтр по тегу никого не приглушил — кадр 03 не показывает фильтр");
  await shot(page, "03-board.png");

  // 04. Чек-лист: HUD с текущей карточкой и кнопками статусов, на карточках — точки статусов.
  await openBoard();
  const current = page
    .locator(".qnode")
    .filter({ has: page.locator('.qnode__status[data-status="review"]') })
    .first();
  await current.locator(".qnode__title").click();
  await page.waitForSelector(".hud", { timeout: 5000 });
  await page.waitForSelector(".drawer", { timeout: 5000 });
  await page.keyboard.press("Escape"); // закрыть drawer; «текущая» карточка остаётся в HUD
  await settle(page, 400);
  if ((await page.locator(".hud").count()) !== 1) throw new Error("Esc снял и HUD — кадр 04 нечего показывать");
  await zoomAt(page, await page.locator(".qnode--current").boundingBox());
  const pane = await page.locator(".react-flow__pane").boundingBox();
  await page.mouse.move(pane.x + pane.width / 2, pane.y + pane.height / 2);
  await page.mouse.down();
  await page.mouse.move(pane.x + pane.width / 2 + 90, pane.y + pane.height / 2, { steps: 10 });
  await page.mouse.up();
  await settle(page, 500);
  await shot(page, "04-checklist.png");

  // 05. Drawer рядом с доской: вопрос, ответ с подсветкой кода и три кнопки статуса.
  await openBoard();
  const answerCard = page
    .locator(".qnode")
    .filter({ has: page.locator(".qnode__title", { hasText: "Mutable default arguments" }) })
    .first();
  await zoomAt(page, await answerCard.boundingBox());
  await answerCard.locator(".qnode__title").click();
  await page.waitForSelector(".drawer", { timeout: 5000 });
  await page.waitForSelector(".drawer__scoring .statusbtn--known", { timeout: 5000 });
  await settle(page, 700);
  await shot(page, "05-drawer.png");

  // 06. Задача на весь экран: условие, стартовый код, эталон и критерии.
  await page.keyboard.press("Escape");
  await openBoard();
  const taskCard = page
    .locator(".qnode", { has: page.locator(".qnode__kind--task") })
    .filter({ has: page.locator(".qnode__title", { hasText: "Fix a skewed Spark join" }) })
    .first();
  await taskCard.locator(".qnode__title").click();
  await page.waitForSelector(".drawer", { timeout: 5000 });
  await page.locator(".drawer__actions button", { hasText: "Full screen" }).click();
  await page.waitForSelector(".drawer--full", { timeout: 5000 });
  await settle(page, 700);
  await shot(page, "06-task.png");

  // 07. Банк вопросов: поиск по всему банку с раскрытым ответом.
  await page.keyboard.press("Escape");
  await page.goto(`${BASE}/#/bank/${POOL}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".bankbrowser--embedded", { timeout: 10000 });
  await page.locator(".bankbrowser__search").fill("spark");
  await settle(page, 400);
  await page
    .locator(".bankrow", { has: page.locator("text=Repartition versus coalesce") })
    .first()
    .locator(".bankrow__head")
    .click();
  await page.waitForSelector(".bankrow--open .bankrow__body", { timeout: 5000 });
  await settle(page, 500);
  await shot(page, "07-bank.png");

  // 10. Мастер направления, шаг «структура»: колонки, под-колонки, палитра, drag & drop.
  await page.goto(BASE + "/#/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".poolcard", { timeout: 10000 });
  await page.locator(`.poolcard[data-pool="${POOL}"] .poolcard__menu`).click();
  await page.locator(`.poolcard[data-pool="${POOL}"] .poolcard__edit`).click();
  await page.waitForSelector(".poolform", { timeout: 5000 });
  await page.locator(".wizard__next").click();
  await page.waitForSelector(".struct__section", { timeout: 5000 });
  await settle(page, 600);
  await shot(page, "10-structure.png");
  await page.keyboard.press("Escape");

  // 11. Тёмная тема.
  await openBoard({ theme: "dark" });
  await frameBoard(page, { zoomOut: 0, panLeft: 0 });
  await shot(page, "11-board-dark.png");

  await browser.close();
  await writeFile(
    path.join(OUTDIR, "README.md"),
    "Screenshots are produced by `frontend/shots.mjs` (`npm run shots`) against the English demo\n" +
      "content in `demo/content-en`, on a seeded checklist: about 60% of the track's cards carry a\n" +
      "known / review / unknown status, picked deterministically from the card id so reruns give the\n" +
      "same frames. See the header of `shots.mjs` for the two commands.\n",
  );
  console.log("готово →", OUTDIR);
}

await main();
