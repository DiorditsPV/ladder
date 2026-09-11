// Headless smoke-тест реального рантайма: демо без входа (стартовый экран, демо-доска, чек-лист
// в браузере, EN-перевод), вход, доска, карточка (по центру / справа), чек-лист, банк, аккаунты («Люди», viewer).
// Запуск: node smoke.mjs   (сервер должен слушать http://localhost:8000; свежая БД — см. CLAUDE.md)
import { chromium } from "playwright";

const URL = process.env.SMOKE_URL || "http://localhost:8000/";
const OWNER_EMAIL = process.env.SMOKE_OWNER_EMAIL || "owner@interview.local";
const OWNER_PASSWORD = process.env.SMOKE_OWNER_PASSWORD || "interview-dev";
const fail = (m) => { console.error("FAIL:", m); process.exit(1); };

const browser = await chromium.launch();
// 1440×900 — опорный размер владельца. Окно карточки по центру шириной min(760px, 58vw): рядом с ним
// текущая карточка доски (280px) помещается только от ~1330px ширины — на 1280 проверка «не под окном»
// по месту по умолчанию была бы невыполнима по построению.
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
// У «Failed to load resource» адрес запроса — в location(): по нему отличаем штатный 401 проверки
// сессии (/api/auth/me без входа — демо-режим) от настоящих ошибок.
page.on("console", (m) => m.type() === "error" && errors.push(`${m.text()} @ ${m.location()?.url ?? ""}`));
page.on("pageerror", (e) => errors.push(String(e)));
const unexpectedErrors = () => errors.filter((e) => !(e.includes("status of 401") && e.includes("/api/auth/me")));

// topbar-settings: тумблеры отображения — в боковой панели (.setdrawer) под ⚙; кнопка ⚙ (.setbtn) — в шапке
// доски рядом с темой (решение владельца 2026-09-11). Каждое переключение = ⚙ → чип → Esc.
// Esc закрывает панель (перехватывается в capture-фазе внутри SettingsMenu), поэтому дожидаемся её
// исчезновения перед следующим шагом.
async function openSettings() {
  await page.locator(".topbar .setbtn").click();
  await page.waitForSelector(".setdrawer", { timeout: 3000 });
}
async function toggleSetting(label) {
  await openSettings();
  await page.locator(".setdrawer .tb__toggle", { hasText: label }).click();
  await page.keyboard.press("Escape");
  await page.waitForSelector(".setdrawer", { state: "detached", timeout: 3000 });
}
// filtersOpen персистится в localStorage между маунтами доски: панель фильтров (справа канвы)
// иногда перекрывает карточку, по которой кликает следующий шаг. Закрыть, если открыта.
async function closeFiltersIfOpen() {
  if ((await page.locator(".filterpanel").count()) > 0) {
    await page.locator(".fp__close").click();
    await page.waitForSelector(".filterpanel", { state: "detached", timeout: 3000 });
  }
}

// 0. Демо-режим (spec 2026-09-11): без входа — стартовый экран, демо-главная (только демо-направления),
//    доска с чек-листом в localStorage, смена языка ведёт на перевод направления.
await page.goto(URL, { waitUntil: "networkidle" });
await page.waitForSelector(".landing__demo", { timeout: 10000 });
const loginFont = await page.$eval(".landing__login", (el) => parseFloat(getComputedStyle(el).fontSize));
if (loginFont > 13) fail(`landing: «Вход» слишком заметен (font-size ${loginFont}px)`);
console.log(`OK: landing — demo first, «Вход» is quiet (${loginFont}px)`);
const themeOf = () => page.evaluate(() => document.documentElement.dataset.theme);
if ((await themeOf()) !== "light") fail(`theme: по умолчанию должна быть светлая, а не ${await themeOf()}`);
await page.locator(".landing .themebtn").click();
if ((await themeOf()) !== "dark") fail("theme: переключатель на стартовом экране не включил тёмную");
await page.click(".landing__demo");
await page.waitForSelector('.poolcard[data-pool="data-engineer"]', { timeout: 10000 });
if ((await themeOf()) !== "dark") fail("theme: на демо-главной тема не совпала со стартовым экраном");
await page.locator(".pageshell .themebtn").click();
if ((await themeOf()) !== "light") fail("theme: переключатель в шапке главной не вернул светлую");
console.log("OK: theme — light by default, one theme across pages, toggle in every header");
await page.waitForSelector('.poolcard[data-pool="data-engineer"]', { timeout: 10000 });
if ((await page.locator('.poolcard[data-pool="system-analyst"]').count()) !== 1) fail("demo: нет системного аналитика");
// В репозитории только пресеты (spec content-in-db): на демо-главной ровно два направления.
if ((await page.locator(".poolcard").count()) !== 2) fail("demo: на главной не ровно два демо-направления");
if ((await page.locator('.poolcard[data-pool$="-en"]').count()) !== 0) fail("demo RU: на главной видны EN-переводы");
if ((await page.locator(".home__add, .poolcard__menu").count()) !== 0) fail("demo: видна правка направлений");
console.log("OK: landing → demo home (DE + SA, no editing)");
// Закрытое входом направление → демо-главная без плашки «Направления нет».
for (const path of ["#/board/private-pool", "#/bank/private-pool"]) {
  await page.goto(URL + path, { waitUntil: "networkidle" });
  await page.waitForURL(/#\/demo$/, { timeout: 5000 }).catch(() => fail(`demo: ${path} не увёл на #/demo`));
  await page.waitForSelector('.poolcard[data-pool="data-engineer"]', { timeout: 5000 });
  if ((await page.locator(".errbar").count()) !== 0) fail(`demo: ${path} показал плашку`);
}
console.log("OK: demo — closed pools lead to the demo home");
// Карточку выбираем по заголовку (как шаги ниже): порядок нод в DOM не совпадает с раскладкой,
// первая по DOM может оказаться за кадром.
await page.click('.poolcard[data-pool="data-engineer"] .poolcard__open');
await page.waitForSelector(".react-flow__node-question", { timeout: 15000 });
await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().click();
await page.waitForSelector(".drawer", { timeout: 5000 });
if ((await page.locator(".drawer__delete, .drawer__edit").count()) !== 0) fail("demo: в drawer есть удаление/правка");
if ((await page.locator(".drawer__hide").count()) !== 1) fail("demo: пропало локальное «Скрыть» в drawer");
await page.keyboard.press("1");
await page.waitForSelector('.qnode__status[data-status="known"]', { timeout: 3000 });
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector('.qnode__status[data-status="known"]', { timeout: 15000 })
  .catch(() => fail("demo: отметка не пережила перезагрузку (localStorage)"));
console.log("OK: demo checklist persists in the browser");
// Смена языка на доске → парное направление. Hash меняется раньше перерисовки: ждём и адрес,
// и заголовок доски перевода — иначе проверки ниже увидят ещё старую доску.
await page.click(".langswitch");
await page.waitForURL(/#\/board\/data-engineer-en$/, { timeout: 10000 })
  .catch(() => fail("demo: EN не переключил на перевод направления"));
await page.waitForFunction(() => document.querySelector(".appname")?.textContent === "Data Engineer", null, { timeout: 10000 })
  .catch(() => fail("demo: доска перевода не отрисовалась"));
await page.waitForSelector(".react-flow__node-question", { timeout: 15000 });
const cyrTitles = (await page.locator(".qnode__title").allInnerTexts()).filter((s) => /[а-яё]/i.test(s));
if (cyrTitles.length) fail(`demo EN: карточки не переведены: ${cyrTitles.slice(0, 3).join(" | ")}`);
await page.click(".langswitch");
await page.waitForURL(/#\/board\/data-engineer$/, { timeout: 10000 }).catch(() => fail("demo: RU не вернул оригинал"));
await page.waitForFunction(() => document.querySelector(".appname")?.textContent === "Дата-инженер", null, { timeout: 10000 })
  .catch(() => fail("demo: доска оригинала не отрисовалась"));
console.log("OK: demo language switch uses the translation and back");
const demoErrors = unexpectedErrors();
if (demoErrors.length) fail(`demo: console/page errors:\n${demoErrors.join("\n")}`);

// 0a. Вход — по #/login (ссылка «Вход» на стартовом экране); после входа — полный режим.
await page.goto(URL + "#/login", { waitUntil: "networkidle" });
await page.waitForSelector(".login__card", { timeout: 10000 });
await page.fill('.login__input[type="email"]', OWNER_EMAIL);
await page.fill('.login__input[type="password"]', OWNER_PASSWORD);
await page.click(".login__card button[type=submit]");
console.log("OK: logged in as owner");
// Демо-часть штатно ловила 401 на /api/auth/me (сессии нет) и уже проверена выше — сбрасываем.
errors.length = 0;

// 0b. Главное меню (pools-main-menu): направления как входы; клик по DE открывает доску.
await page.waitForSelector(".poolcard", { timeout: 10000 });
const poolCards = await page.locator(".poolcard").count();
if (poolCards < 1) fail("main menu shows no pools");
const deCard = page.locator('.poolcard[data-pool="data-engineer"]');
if ((await deCard.count()) !== 1) fail("data-engineer pool card missing on main menu");
// 0c. Мастер направления (pool-wizard): шаг 1 (название + пресет DE) → шаг 2 (в редакторе 4 раздела
//     пресета) → шаг 3 (предпросмотр) → «Создать» → карточка с тем же числом вопросов, что у DE.
const deMeta = await deCard.locator(".poolcard__stat").first().innerText();
await page.locator(".home__add").click();
await page.waitForSelector(".poolform", { timeout: 3000 });
await page.fill(".poolform__label", "Smoke Pool");
await page.locator(".pool-preset").selectOption("data-engineer");
await page.locator(".wizard__next").click();
await page.waitForFunction(() => document.querySelectorAll(".struct__section").length === 4, null, { timeout: 3000 });
await page.locator(".wizard__next").click();
await page.waitForSelector(".wizard__preview", { timeout: 3000 });
if (!(await page.locator(".wizard__preview").innerText()).includes("ФРЕЙМВОРКИ")) fail("wizard preview lacks FRAMEWORKS section");
await page.locator(".poolform__submit").click();
await page.waitForSelector('.poolcard[data-pool="smoke-pool"]', { timeout: 10000 });
const smokeMeta = await page.locator('.poolcard[data-pool="smoke-pool"] .poolcard__stat').first().innerText();
if (smokeMeta.split("·")[0].trim() !== deMeta.split("·")[0].trim()) fail(`preset copy mismatch: "${smokeMeta}" vs "${deMeta}"`);
console.log("OK: pool wizard — created from preset via 3 steps");
// Переименование: тот же мастер в режиме edit, «Далее» ×2 → «Сохранить».
const smokeCard = page.locator('.poolcard[data-pool="smoke-pool"]');
await smokeCard.locator(".poolcard__menu").click();
await smokeCard.locator(".poolcard__edit").click();
await page.waitForSelector(".poolform", { timeout: 3000 });
await page.fill(".poolform__label", "Smoke Pool 2");
await page.locator(".wizard__next").click();
await page.locator(".wizard__next").click();
await page.locator(".poolform__submit").click();
await page.waitForFunction(
  () => document.querySelector('.poolcard[data-pool="smoke-pool"] .poolcard__label')?.textContent === "Smoke Pool 2",
  null,
  { timeout: 5000 },
);
// 0c'. Структурный редактор: добавить раздел «Продажи» с подкатегорией «Холодные», перетащить его
//      на первое место (HTML5 DnD за ⠿) → предпросмотр → «Сохранить» → чип первый на карточке,
//      раздел первый на доске направления и под-колонка на месте.
const chipsBefore = await smokeCard.locator(".poolcard__block").count();
const nodesBefore = parseInt(await smokeCard.locator(".poolcard__stat").first().innerText(), 10);
await smokeCard.locator(".poolcard__menu").click();
await smokeCard.locator(".poolcard__edit").click();
await page.waitForSelector(".poolform", { timeout: 3000 });
await page.locator(".wizard__next").click();
await page.waitForSelector(".struct", { timeout: 3000 });
await page.locator(".struct__addsection").click();
await page.locator(".struct__name").last().fill("Продажи");
await page.locator(".struct__section").last().locator(".struct__addsub").click();
await page.locator(".struct__subname").last().fill("Холодные");
// Не locator.dragTo(): hover цели прокручивает тело мастера ДО первого движения мыши, а Chromium
// ищет draggable по позиции mousedown — после прокрутки там уже другой элемент и drag не начинается.
// Поэтому: зажать ⠿ → сдвиг на 8px (drag стартовал) → hover цели (теперь прокрутка безопасна) → отпустить.
const grip = page.locator(".struct__section").last().locator(".struct__grip");
await grip.hover();
await page.mouse.down();
const gripBox = await grip.boundingBox();
await page.mouse.move(gripBox.x + gripBox.width / 2, gripBox.y + gripBox.height / 2 + 8);
await page.locator(".struct__section").first().hover();
await page.mouse.up();
await page.waitForFunction(() => document.querySelector(".struct__name")?.value === "Продажи", null, { timeout: 3000 });
await page.locator(".wizard__next").click();
await page.waitForSelector(".wizard__preview", { timeout: 3000 });
const previewText = await page.locator(".wizard__preview").innerText();
if (!previewText.includes("ПРОДАЖИ") || !previewText.includes("Холодные")) fail(`wizard preview lacks new section/sub: ${JSON.stringify(previewText)}`);
await page.locator(".poolform__submit").click();
await page.waitForFunction(
  () => document.querySelector('.poolcard[data-pool="smoke-pool"] .poolcard__block')?.textContent === "Продажи",
  null,
  { timeout: 5000 },
);
if ((await smokeCard.locator(".poolcard__block").count()) !== chipsBefore + 1) fail("section chip count did not grow by one");
await page.goto(URL + "#/board/smoke-pool");
await page.waitForSelector(".bgroup__header", { timeout: 10000 });
const smokeHeaders = await page.locator(".bgroup__header").allInnerTexts();
if (!smokeHeaders[0]?.toLowerCase().includes("продажи")) fail(`board: dragged section is not first: ${JSON.stringify(smokeHeaders)}`);
const smokeSubs = await page.locator(".subhead").allInnerTexts();
if (!smokeSubs.some((s) => s.includes("Холодные"))) fail(`board lacks new sub-column: ${JSON.stringify(smokeSubs)}`);
console.log("OK: structure editor — section + subcategory added, drag & drop reordered, board shows them");
await page.goto(URL + "#/");
await page.waitForSelector('.poolcard[data-pool="smoke-pool"]', { timeout: 10000 });
// Удаление раздела с вопросами (второй в списке — бывший первый DE): confirm с числом вопросов.
await smokeCard.locator(".poolcard__menu").click();
await smokeCard.locator(".poolcard__edit").click();
await page.waitForSelector(".poolform", { timeout: 3000 });
await page.locator(".wizard__next").click();
await page.waitForSelector(".struct", { timeout: 3000 });
await page.locator(".struct__section").nth(1).locator(".struct__menu").click();
let colConfirm = "";
page.once("dialog", (d) => {
  colConfirm = d.message();
  d.accept();
});
await page.locator(".struct__del").click(); // ждёт enabled: счётчики вопросов подгружаются
if (!/\(\d+\)/.test(colConfirm)) fail(`expected confirm with question count, got: "${colConfirm}"`);
await page.waitForFunction((n) => document.querySelectorAll(".struct__section").length === n, chipsBefore, { timeout: 3000 });
await page.locator(".wizard__next").click();
await page.locator(".poolform__submit").click();
await page.waitForFunction(
  (n) => document.querySelectorAll('.poolcard[data-pool="smoke-pool"] .poolcard__block').length === n,
  chipsBefore,
  { timeout: 5000 },
);
const nodesAfter = parseInt(await smokeCard.locator(".poolcard__stat").first().innerText(), 10);
if (!(nodesAfter < nodesBefore)) fail(`deleting a section did not drop questions: ${nodesBefore} → ${nodesAfter}`);
console.log(`OK: structure editor — section deleted with confirm, questions ${nodesBefore} → ${nodesAfter}`);

// 0c''. «Дублировать» в меню карточки DE: копия «Дата-инженер (копия)» (id — транслитерация) с той же
//       статистикой вопросов; затем удаляем копию через меню.
await deCard.locator(".poolcard__menu").click();
await deCard.locator(".poolcard__dup").click();
await page.waitForSelector('.poolcard[data-pool^="data-inzhener"]', { timeout: 10000 });
const dupCard = page.locator('.poolcard[data-pool^="data-inzhener"]').first();
const dupId = await dupCard.getAttribute("data-pool");
const dupMeta = await dupCard.locator(".poolcard__stat").first().innerText();
if (dupMeta.split("·")[0].trim() !== deMeta.split("·")[0].trim()) fail(`duplicate mismatch: "${dupMeta}" vs "${deMeta}"`);
if (!(await dupCard.locator(".poolcard__label").innerText()).includes("(копия)")) fail("duplicate label lacks «(копия)»");
page.once("dialog", (d) => d.accept());
await dupCard.locator(".poolcard__menu").click();
await dupCard.locator(".poolcard__delete").click();
await page.waitForSelector(`.poolcard[data-pool="${dupId}"]`, { state: "detached", timeout: 5000 });
console.log(`OK: duplicate — ${dupId} created with DE stats and deleted`);

// 0c'''. «Обновить из файлов» — только у пресетов (has_files): у DE есть, у smoke-pool (создан в UI) нет;
//        на свежей БД предпросмотр (dry_run) правок не находит и подтверждение не спрашивает.
await smokeCard.locator(".poolcard__menu").click();
if ((await smokeCard.locator(".poolcard__sync").count()) !== 0) fail("reload from files shown for a pool without files");
await deCard.locator(".poolcard__menu").click();
await deCard.locator(".poolcard__sync").click();
await page.waitForFunction(
  () => document.querySelector(".errbar--ok")?.textContent?.includes("совпадает с файлами"),
  null,
  { timeout: 5000 },
);
console.log("OK: reload from files — presets only, no-op preview on a fresh DB");

page.once("dialog", (d) => d.accept());
await smokeCard.locator(".poolcard__menu").click();
await smokeCard.locator(".poolcard__delete").click();
await page.waitForSelector('.poolcard[data-pool="smoke-pool"]', { state: "detached", timeout: 5000 });
console.log("OK: pool create from preset / rename / delete");

// 0d. RU/EN (i18n): переключатель на главной меняет опорные подписи и возвращает обратно
//     (язык хранится в localStorage — обязательно вернуть RU, остальные шаги идут по русским строкам).
await page.locator(".langswitch").first().click();
await page.waitForFunction(() => document.querySelector(".home__h2")?.textContent === "Tracks", null, { timeout: 3000 });
if ((await page.locator(".poolcard__start").first().innerText()) !== "Question bank") fail("EN: bank button not translated");
await page.locator(".langswitch").first().click();
await page.waitForFunction(() => document.querySelector(".home__h2")?.textContent === "Направления", null, { timeout: 3000 });
console.log("OK: RU/EN switch");

// Кликаем по самой ссылке-«растяжке» (.poolcard__label), а не по всей карточке: внутри есть ещё
// сиблинг .poolcard__open (ссылка на вопросы) — клик по центру div'а рискует попасть мимо доски.
// После переходов шага 0c' на доску и обратно убеждаемся, что мы снова на главной.
await page.waitForSelector('.poolcard[data-pool="data-engineer"]', { timeout: 5000 });
await deCard.locator(".poolcard__label").click();
await page.waitForFunction(() => location.hash.startsWith("#/board/data-engineer"), null, { timeout: 5000 });
console.log(`OK: main menu lists ${poolCards} pool(s), DE opens the board`);

// 1. Граф отрисовался: есть кастомные ноды.
await page.waitForSelector(".qnode", { timeout: 10000 });
const nodeCount = await page.locator(".qnode").count();
if (nodeCount < 5) fail(`too few nodes rendered: ${nodeCount}`);
console.log(`OK: rendered ${nodeCount} nodes`);

// 1a. board-toolbar: панель фильтров по умолчанию закрыта и открывается кнопкой toolbar'а.
//     Открываем один раз и держим открытой (состояние персистится в localStorage) — на неё
//     завязаны шаги с .fp__* ниже.
if ((await page.locator(".filterpanel").count()) !== 0) fail("filter panel must be closed by default");
await page.locator(".topbar .filtersbtn").click();
await page.waitForSelector(".filterpanel", { timeout: 3000 });
if ((await page.locator(".topbar .filtersbtn").getAttribute("aria-pressed")) !== "true") fail("filters button not pressed after opening");
console.log("OK: filter panel opens from the toolbar");

// 1b. Swimlane: 4 заголовка блоков + под-колонки фреймворков + 4 метки оси сложности (base/junior/middle/senior).
const groups = await page.locator(".bgroup__header").count();
if (groups !== 4) fail(`expected 4 block headers, got ${groups}`);
const subs = await page.locator(".subhead").count();
if (subs < 4) fail(`expected >=4 sub-columns (frameworks split), got ${subs}`);
const bands = await page.locator(".bands__label").count();
if (bands !== 4) fail(`expected 4 difficulty band labels, got ${bands}`);
console.log(`OK: ${groups} blocks + ${subs} sub-columns + ${bands} difficulty bands`);

// 2. Ноды видимы в кадре (fitView отработал — bbox внутри вьюпорта).
const box = await page.locator(".qnode").first().boundingBox();
if (!box || box.y < 0 || box.x < 0) fail(`first node off-screen: ${JSON.stringify(box)}`);
console.log(`OK: first node in viewport at (${Math.round(box.x)}, ${Math.round(box.y)})`);

// 3. Клик по карточке открывает её — по умолчанию по центру доски (режим center). Ответ виден сразу
//    (решение владельца 2026-09-11: «Показать ответ» убрано) — читаем тело целиком, как из панели.
await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().click();
await page.waitForSelector(".drawer", { timeout: 5000 });
if ((await page.locator(".drawer.drawer--center").count()) !== 1) fail("card must open in the center by default");
if ((await page.locator(".drawer__answer").count()) !== 1 || (await page.locator(".drawer__reveal").count()) !== 0) {
  fail("center card must show the answer right away, without «Показать ответ»");
}
const drawerText = await page.locator(".drawer__body").innerText();
if (drawerText.length < 50) fail("drawer body too short");
console.log("OK: drawer opened with content");

// 3b. Клик задаёт «текущую карточку». Пока карточка открыта по центру, HUD скрыт (заголовок и статусы —
//     в самой карточке); Esc закрывает карточку, курсор остаётся — HUD показывает текущий вопрос.
if ((await page.locator(".hud").count()) !== 0) fail("HUD must be hidden while the center card is open");
await page.keyboard.press("Escape");
await page.waitForSelector(".drawer", { state: "detached", timeout: 3000 });
await page.waitForSelector(".hud", { timeout: 3000 });
const hudTitle = await page.locator(".hud__title").innerText();
if (!hudTitle.includes("ROW_NUMBER")) fail(`HUD shows wrong question: ${hudTitle}`);
console.log("OK: HUD shows current question");

// 4. Чек-лист разбора: клик по кнопке «Знаю» в HUD → карточка помечена статусом «знаю».
//    Повторный клик по той же кнопке снимает статус.
const rowNumberCard = page.locator(".qnode").filter({ has: page.locator(".qnode__title", { hasText: "ROW_NUMBER" }) });
await page.locator(".hud__score .statusbtn--known").click();
await page.waitForSelector('.qnode__status[data-status="known"]', { timeout: 3000 });
if ((await rowNumberCard.locator('.qnode__status[data-status="known"]').count()) !== 1) fail("HUD status button did not mark ROW_NUMBER as known");
console.log("OK: status applied via HUD (known)");
await page.locator(".hud__score .statusbtn--known").click(); // повтор — снимает
await rowNumberCard
  .locator('.qnode__status[data-status="known"]')
  .waitFor({ state: "detached", timeout: 3000 })
  .catch(() => fail("repeat click on HUD status button did not clear the status"));
console.log("OK: repeat click on HUD status clears it");

// 5. Карточка показывает короткий заголовок (title), а не полный текст вопроса.
const cardText = await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().innerText();
if (cardText.length > 60) fail(`card shows full question, not short title: "${cardText}"`);
console.log(`OK: card shows short title ("${cardText}")`);

// 5b. Фильтр по тегам: клик по тегу гасит нерелевантные ноды.
await page.locator(".fp__tag", { hasText: "optimization" }).first().click();
await page.waitForTimeout(300);
const dimmed = await page.locator(".qnode--dimmed").count();
if (dimmed < 1) fail("tag filter did not dim any nodes");
console.log(`OK: tag filter dims ${dimmed} non-matching nodes`);
await page.locator(".fp__clear").click(); // сброс тегов

// 5c. Фильтр по типу (вопрос/задача): выключение «вопрос» гасит вопросные ноды.
// (Селектор направлений/треков убран ещё в Task 8; «.iv-pick» — см. шаг 10.)
await page.locator(".fp__chip", { hasText: "вопрос" }).click();
await page.waitForTimeout(250);
const dimmedByKind = await page.locator(".qnode--dimmed").count();
if (dimmedByKind < 1) fail("kind filter did not dim any nodes");
await page.locator(".fp__chip", { hasText: "вопрос" }).click(); // вернуть
console.log(`OK: kind filter dims ${dimmedByKind} nodes`);

// 6. «n» уводит к следующей неразобранной карточке (в том числе с последней в колонке).
//    Клик открывает карточку по центру (HUD скрыт) — закрываем её Esc, курсор остаётся на карточке.
await page.locator(".qnode__title", { hasText: "KubernetesExecutor" }).first().click();
await page.waitForSelector(".drawer", { timeout: 3000 });
await page.keyboard.press("Escape");
await page.waitForSelector(".hud", { timeout: 3000 });
const beforeNext = await page.locator(".hud__title").innerText();
await page.keyboard.press("n");
await page.waitForTimeout(500);
const afterNext = await page.locator(".hud__title").innerText();
if (afterNext === beforeNext) fail("«n» stuck on the current card");
console.log("OK: «n» advances to the next unreviewed card");

// 6b. Настройки отображения (topbar-settings): панель под ⚙ (кнопка в шапке) открывается и содержит
// тумблеры направляющих, точек-фона, скрытых и таймера; повторный клик по ⚙ её закрывает.
await openSettings();
const tbBtns = await page.locator(".setdrawer .tb__toggle").count();
if (tbBtns < 6) fail(`display toggles missing in settings drawer (got ${tbBtns})`);
await page.locator(".topbar .setbtn").click();
await page.waitForSelector(".setdrawer", { state: "detached", timeout: 3000 })
  .catch(() => fail("second click on ⚙ must close the settings drawer"));
const vBefore = await page.locator(".guides__v").count();
if (vBefore !== 0) fail(`vertical guides should be off by default (got ${vBefore})`);
await toggleSetting("Верт"); // включить вертикальные
await page.waitForTimeout(200);
const vAfter = await page.locator(".guides__v").count();
if (vAfter < 1) fail("vertical guides did not toggle on");
const bgDefault = await page.locator(".react-flow__background").count();
if (bgDefault !== 0) fail(`background should be off by default (got ${bgDefault})`);
await toggleSetting("Точки"); // включить точки
await page.waitForTimeout(200);
const bgDots = await page.locator(".react-flow__background").count();
if (bgDots < 1) fail("dots background not shown after toggling icon");
console.log(`OK: settings drawer (${tbBtns} toggles) switches guides + dots grid (default off)`);

// 6c. Оформления (решение владельца 2026-09-11): в ⚙ ровно два — «Брутализм в цвете» (37) и «Изыскания» (58);
//     по умолчанию (чистый localStorage) активно «Изыскания». Переключение меняет data-design и запоминается.
await openSettings();
const designs = await page.locator(".setdrawer .design__opt").evaluateAll((els) =>
  els.map((e) => ({ id: e.dataset.design, label: e.textContent.trim(), on: e.getAttribute("aria-checked") === "true" })));
if (designs.map((d) => d.id).join(",") !== "37,58") fail(`⚙ must offer exactly two designs (37, 58): ${JSON.stringify(designs)}`);
if (designs.map((d) => d.label).join(" | ") !== "Брутализм в цвете | Изыскания") fail(`design labels: ${JSON.stringify(designs)}`);
if (designs.filter((d) => d.on).map((d) => d.id).join(",") !== "58") fail(`«Изыскания» must be active by default: ${JSON.stringify(designs)}`);
const designOf = () => page.evaluate(() => document.documentElement.dataset.design);
if ((await designOf()) !== "58") fail(`default data-design must be 58, got ${await designOf()}`);
await page.locator('.setdrawer .design__opt[data-design="37"]').click();
if ((await designOf()) !== "37" || (await page.evaluate(() => localStorage.getItem("design"))) !== "37") fail("switching to «Брутализм в цвете» did not apply/store 37");
await page.locator('.setdrawer .design__opt[data-design="58"]').click();
if ((await designOf()) !== "58" || (await page.evaluate(() => localStorage.getItem("design"))) !== "58") fail("switching back to «Изыскания» did not apply/store 58");
await page.keyboard.press("Escape");
await page.waitForSelector(".setdrawer", { state: "detached", timeout: 3000 });
console.log("OK: ⚙ offers two designs, «Изыскания» (58) by default, switching applies and stores");


// 8. Тема: переключатель в шапке доски меняет data-theme (и обратно); в ⚙ его больше нет.
const before = await page.evaluate(() => document.documentElement.dataset.theme || "light");
await page.locator(".topbar .themebtn").click();
const after = await page.evaluate(() => document.documentElement.dataset.theme);
if (after === before) fail(`theme toggle did not change theme (${before} → ${after})`);
await page.locator(".topbar .themebtn").click();
if ((await page.evaluate(() => document.documentElement.dataset.theme)) !== before) fail("theme toggle did not switch back");
await openSettings();
if ((await page.locator(".setdrawer .themebtn").count()) !== 0) fail("theme toggle must live in the header, not in ⚙");
await page.keyboard.press("Escape");
await page.waitForTimeout(200);
console.log(`OK: theme toggles in the header (${before} → ${after} → ${before})`);

// --- Накопленные проверки фич. Порядок важен: локально-стейтовые (таймер/поиск/чек-лист)
//  идут до шага 21, который делает page.reload() и стирает накопленное состояние.

// 9b. Таймер разбора: по умолчанию скрыт (topbar-settings), включается тумблером в ⚙ — и тикает.
// Закрыть карточку, если открыта с предыдущих шагов: Esc без открытой карточки снял бы текущую, а с ней и HUD.
if ((await page.locator(".drawer").count()) > 0) {
  await page.keyboard.press("Escape");
  await page.waitForSelector(".drawer", { state: "detached", timeout: 3000 });
}
await page.waitForSelector(".hud", { timeout: 3000 }); // таймер живёт в HUD текущей карточки
if ((await page.locator(".hud__timer").count()) !== 0) fail("HUD timer must be hidden by default");
await toggleSetting("Таймер");
await page.waitForSelector(".hud__timer", { timeout: 3000 });
const tmr1 = (await page.locator(".hud__timer").first().innerText()).trim();
if (!/\d+:\d{2}/.test(tmr1)) fail(`timer format wrong: "${tmr1}"`);
await page.waitForTimeout(1300);
const tmr2 = (await page.locator(".hud__timer").first().innerText()).trim();
if (tmr2 === tmr1) fail(`timer not ticking (${tmr1} == ${tmr2})`);
await toggleSetting("Таймер"); // вернуть в скрытое состояние (дефолт)
if ((await page.locator(".hud__timer").count()) !== 0) fail("HUD timer did not hide again");
console.log(`OK: HUD timer hidden by default, ticks when enabled (${tmr1} → ${tmr2})`);

// 9c. Поиск по вопросам: запрос гасит несовпавшие ноды; очистка убирает гашение.
// (После клавиатурных проверок: фокус уходит в input — дальше body-клавиатура не нужна.)
const search = page.locator(".fp__search");
await search.fill("MergeTree");
await page.waitForTimeout(300);
const dimSearch = await page.locator(".qnode--dimmed").count();
if (dimSearch < 1) fail("search did not dim non-matching nodes");
await search.fill("");
await page.waitForTimeout(300);
const dimCleared = await page.locator(".qnode--dimmed").count();
if (dimCleared >= dimSearch) fail(`clearing search did not remove dim (${dimSearch} → ${dimCleared})`);
console.log(`OK: question search dims ${dimSearch}, clears to ${dimCleared}`);

// 9d. Прогресс-фильтр — ровно один чип «Только неразобранное» (чипа оценок больше нет).
await page.waitForSelector(".filterpanel", { timeout: 3000 });
if ((await page.locator(".fp__chip", { hasText: "Только неразобранное" }).count()) !== 1) fail("«Только неразобранное» chip missing");
if ((await page.locator(".topbar .progress").count()) !== 0) fail("board toolbar must not carry a progress bar");
console.log("OK: progress filter is the checklist chip only");

// 9f. UX-полировка: HUD-прогресс+топик, чип переполнения тегов, свёртка панели тегов.
await page.waitForSelector(".hud__progress", { timeout: 3000 });
const hudProg = await page.locator(".hud__progress").innerText();
if (!hudProg.includes("/")) fail(`HUD progress missing fraction: "${hudProg}"`);
if (hudProg.replace(/[^·]/g, "").length < 1) fail(`HUD progress missing topic separator: "${hudProg}"`);
console.log(`OK: HUD progress + topic (${hudProg})`);

// Карточка показывает все 1–3 тега (конвенция контента); «+N» — только сверх нормы, поэтому
// на банке DE его быть не должно, а карточки с тремя тегами — должны.
const threeTagCards = await page.locator(".qnode__tags").evaluateAll((els) => els.filter((e) => e.querySelectorAll(".tagchip:not(.tagchip--more)").length === 3).length);
if (threeTagCards < 1) fail("no card renders all three tags");
const moreChips = await page.locator(".tagchip--more").count();
if (moreChips > 0) fail(`tag-overflow chip (+N) rendered although no card has >3 tags (${moreChips})`);
console.log(`OK: cards show all tags (${threeTagCards} with three), no +N chip`);

// board-toolbar: ✕ в панели закрывает её целиком, кнопка toolbar'а открывает обратно — теги на месте.
const tagsBefore = await page.locator(".fp__tag").count();
if (tagsBefore < 1) fail("expected tag chips in filter panel");
await page.locator(".fp__close").click();
await page.waitForSelector(".filterpanel", { state: "detached", timeout: 3000 });
if ((await page.locator(".topbar .filtersbtn").getAttribute("aria-pressed")) !== "false") fail("filters button still pressed after closing");
await page.locator(".topbar .filtersbtn").click();
await page.waitForSelector(".filterpanel", { timeout: 3000 });
const tagsAgain = await page.locator(".fp__tag").count();
if (tagsAgain !== tagsBefore) fail(`filter panel did not restore tags (${tagsAgain} vs ${tagsBefore})`);
console.log(`OK: filter panel close/reopen keeps ${tagsBefore} tags`);

// 9g. Чек-лист (study-progress): «1» ставит статус «знаю» текущей карточке и уводит к следующей;
//     в drawer — кнопки статусов, повторный клик той же кнопки снимает статус.
//     Проверка относительная: после клика число «знаю» меняется на ±1 и возвращается вторым кликом.
await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().click();
await page.waitForSelector(".drawer", { timeout: 3000 });
await page.keyboard.press("1");
await page.waitForSelector('.qnode__status[data-status="known"]', { timeout: 3000 });
if ((await rowNumberCard.locator('.qnode__status[data-status="known"]').count()) !== 1) fail("checklist: known status not on the current card");
const knownAfterKey = await page.locator('.qnode__status[data-status="known"]').count();
await page.waitForSelector(".drawer .statusbtn--known", { timeout: 3000 });
if ((await page.locator(".drawer .drawer__scoring .scorebtn").count()) !== 0) fail("drawer still shows scoring stars");
await page.locator(".drawer .statusbtn--known").click();
await page.waitForFunction((n) => Math.abs(document.querySelectorAll('.qnode__status[data-status="known"]').length - n) === 1, knownAfterKey, { timeout: 3000 });
await page.locator(".drawer .statusbtn--known").click();
await page.waitForFunction((n) => document.querySelectorAll('.qnode__status[data-status="known"]').length === n, knownAfterKey, { timeout: 3000 });
console.log(`OK: checklist — «1» sets status, drawer button toggles it (${knownAfterKey} known)`);
// (после «1» вьюпорт сдвинут к следующей карточке — дальше идёт переход на экран настройки, это не мешает)

// --- pools-main-menu: 13/17 остаются на доске (шпаргалка и toolbar живут только там);
// 12/14/16/18 (банк) выполняются после перехода на страницу #/bank/<pool> — см. ниже.

// 13. Шпаргалка горячих клавиш: «?» открывает оверлей, Esc закрывает.
// (Фокус на body, не в input/textarea — «?» доходит до обработчика.)
await page.keyboard.press("?");
await page.waitForSelector(".help-modal", { timeout: 3000 });
const helpText = await page.locator(".help-modal").innerText();
if (!helpText.includes("неразобранному")) fail(`help overlay missing shortcuts: "${helpText}"`);
await page.keyboard.press("Escape");
await page.waitForSelector(".help-modal", { state: "detached", timeout: 3000 });
console.log("OK: shortcuts help overlay (? opens, Esc closes)");

// 17. board-toolbar: шапка — один ряд: «← Направления», название, фильтры, тема, ⚙, RU/EN, •••;
//     прогресса нет; ⚙ — кнопка в шапке, в ••• только шпаргалка и банк; экспорта и кнопок банка в шапке нет.
const topRows = await page.locator(".topbar > .topbar__row").count();
if (topRows !== 1) fail(`expected exactly 1 topbar row, got ${topRows}`);
if ((await page.locator(".topbar .topbar__back").count()) !== 1) fail("back-to-menu link missing");
if (!(await page.locator(".topbar .appname").innerText()).includes("Дата-инженер")) fail("pool label missing in topbar");
for (const sel of [".filtersbtn", ".themebtn", ".setbtn", ".langswitch", ".morebtn"]) {
  if ((await page.locator(`.topbar ${sel}`).count()) !== 1) fail(`toolbar element ${sel} missing`);
}
if ((await page.locator(".topbar .progress").count()) !== 0) fail("progress bar must not be in the toolbar");
if ((await page.locator(".topbar .addbtn, .topbar .bankbtn, .topbar .exportbtn").count()) !== 0) fail("export/bank buttons must not be in the topbar");
await page.locator(".topbar .morebtn").click();
await page.waitForSelector(".moremenu", { timeout: 3000 });
if ((await page.locator(".moremenu .setbtn").count()) !== 0) fail("settings must not be in the ••• menu (⚙ lives in the toolbar)");
if ((await page.locator(".moremenu .tbmenu__item").count()) !== 2) fail("••• menu must hold only the cheat sheet and the bank link");
if ((await page.locator(".moremenu .helpbtn").count()) !== 1) fail("shortcuts item missing in ••• menu");
if (!(await page.locator(".moremenu .bankLink").getAttribute("href"))?.startsWith("#/bank/data-engineer")) fail("••• menu must link to the question bank");
await page.keyboard.press("Escape");
await page.waitForSelector(".moremenu", { state: "detached", timeout: 3000 });
console.log(`OK: board toolbar (${topRows} row, back link, pool label, filters/theme/⚙/•••; ••• = cheat sheet + bank)`);

// 22. Карточка вопроса — два режима (решение владельца 2026-09-11). По умолчанию — окно по центру доски
//     шириной min(760px, 58vw), под ним лёгкий скрим, доска вокруг видна и кликается (клик по другой
//     карточке переключает её), ответ виден сразу, ‹ › листают матрицу и ставят текущую карточку доски
//     сбоку от окна. Окно тащится за шапку и тянется уголком / правым краем (22a, 22b).
//     «Справа» — панель как раньше; ширина тянется ручкой на левом краю и переживает перезагрузку,
//     двойной клик — ширина по умолчанию. Выбор режима — ещё и в ⚙ «Карточка вопроса».
// Заодно — сохранённое устаревшее оформление (56 «Атлас» убрано) при загрузке превращается в «Изыскания».
await page.evaluate(() => localStorage.setItem("design", "56"));
await page.reload({ waitUntil: "networkidle" }); // чистый старт: карточка закрыта, вьюпорт по умолчанию
await page.waitForSelector(".qnode", { timeout: 10000 });
if ((await page.evaluate(() => document.documentElement.dataset.design)) !== "58") fail("stale design 56 must fall back to 58");
await closeFiltersIfOpen();
await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().click();
const centerCard = page.locator(".drawer.drawer--center");
await centerCard.waitFor({ timeout: 3000 });
const vp = page.viewportSize();
const cardBox = await centerCard.boundingBox();
const defaultCardW = Math.min(760, vp.width * 0.58);
if (Math.abs(cardBox.width - defaultCardW) > 2) fail(`center card default width must be min(760, 58vw) = ${defaultCardW}, got ${Math.round(cardBox.width)}`);
if (Math.abs(cardBox.x + cardBox.width / 2 - vp.width / 2) > 2) fail(`center card must start centered: x=${Math.round(cardBox.x)}`);
if ((await page.locator(".hud").count()) !== 0) fail("HUD must be hidden while the center card is open");
// Скрим под окном: лёгкий (~10% в светлой) и не ловит указатель — доска кликается сквозь него.
const scrim = await page.evaluate(() => {
  const el = document.querySelector(".cardscrim");
  if (!el) return null;
  const cs = getComputedStyle(el);
  const alpha = Number((cs.backgroundColor.match(/rgba?\(([^)]+)\)/)?.[1] ?? "").split(",")[3] ?? 1);
  return { pe: cs.pointerEvents, alpha, z: Number(cs.zIndex), cardZ: Number(getComputedStyle(document.querySelector(".drawer--center")).zIndex) };
});
if (!scrim) fail("no scrim under the center card");
if (scrim.pe !== "none") fail(`scrim must not catch the pointer (pointer-events: ${scrim.pe})`);
if (!(scrim.alpha >= 0.05 && scrim.alpha <= 0.15)) fail(`light-theme scrim must be ~10%, got ${scrim.alpha}`);
if (!(scrim.z < scrim.cardZ)) fail(`scrim must lie under the card window (z ${scrim.z} vs ${scrim.cardZ})`);
// Карточки доски вне центральной: целиком на канве, не погашены и не перекрыты (elementFromPoint
// в их центре попадает в саму карточку — значит, видны и кликабельны).
const around = await page.evaluate(() => {
  const card = document.querySelector(".drawer--center").getBoundingClientRect();
  const pane = document.querySelector(".react-flow").getBoundingClientRect();
  const hits = [];
  for (const el of document.querySelectorAll(".react-flow__node-question")) {
    if (el.querySelector(".qnode--dimmed")) continue;
    const r = el.getBoundingClientRect();
    const inPane = r.left >= pane.left && r.right <= pane.right && r.top >= pane.top && r.bottom <= pane.bottom;
    const overlaps = !(r.right <= card.left || r.left >= card.right || r.bottom <= card.top || r.top >= card.bottom);
    if (!inPane || overlaps) continue;
    const x = r.left + r.width / 2;
    const y = r.top + r.height / 2;
    if (!el.contains(document.elementFromPoint(x, y))) continue;
    hits.push({ x, y, title: el.querySelector(".qnode__title")?.textContent?.trim() ?? "" });
  }
  return hits;
});
if (around.length < 3) fail(`board cards around the center card are not visible (${around.length})`);
console.log(`OK: center card ${Math.round(cardBox.width)}px of ${vp.width} (min(760, 58vw)), scrim ${scrim.alpha}, ${around.length} board cards visible around it, HUD hidden`);
const openTitle = await page.locator(".drawer__title").innerText();
const other = around.find((o) => o.title && o.title !== openTitle);
if (!other) fail("no other board card to click around the center card");
await page.mouse.click(other.x, other.y);
await page.waitForFunction((t) => document.querySelector(".drawer__title")?.textContent === t, other.title, { timeout: 3000 })
  .catch(() => fail(`click on a board card did not switch the center card to «${other.title}»`));
console.log(`OK: board stays clickable — «${other.title}» replaced «${openTitle}» in the center card`);
// Ответ виден сразу и на соседних карточках; › / ‹ листают матрицу, а текущая карточка доски после
// перехода стоит сбоку от окна — прямоугольники не пересекаются (setCenter анимируется 400 мс).
if ((await page.locator(".drawer__answer").count()) !== 1) fail("answer must be visible right away");
const besideWindow = () => page.evaluate(() => {
  const a = document.querySelector(".qnode--current")?.getBoundingClientRect();
  const w = document.querySelector(".drawer--center")?.getBoundingClientRect();
  if (!a || !w) return null;
  const hit = !(a.right <= w.left || a.left >= w.right || a.bottom <= w.top || a.top >= w.bottom);
  return { hit, side: a.right <= w.left ? "left" : a.left >= w.right ? "right" : "under" };
});
const t1 = await page.locator(".drawer__title").innerText();
await page.locator(".drawer__next").click();
await page.waitForFunction((t) => document.querySelector(".drawer__title")?.textContent !== t, t1, { timeout: 3000 })
  .catch(() => fail("› did not switch the card"));
const t2 = await page.locator(".drawer__title").innerText();
if ((await page.locator(".drawer__answer").count()) !== 1) fail("answer must be visible on the next card right away");
await page.waitForTimeout(700);
const besideNext = await besideWindow();
if (!besideNext || besideNext.hit) fail(`after › the current board card is under the window: ${JSON.stringify(besideNext)}`);
await page.locator(".drawer__prev").click();
await page.waitForFunction((t) => document.querySelector(".drawer__title")?.textContent === t, t1, { timeout: 3000 })
  .catch(() => fail("‹ did not return to the previous card"));
if ((await page.locator(".drawer__answer").count()) !== 1) fail("answer must be visible after ‹ as well");
await page.waitForTimeout(700);
const besidePrev = await besideWindow();
if (!besidePrev || besidePrev.hit) fail(`after ‹ the current board card is under the window: ${JSON.stringify(besidePrev)}`);
console.log(`OK: answer visible right away; › / ‹ switch the card («${t1}» → «${t2}» → back), current board card beside the window (${besideNext.side}, ${besidePrev.side})`);

// 22a. Окно по центру тащится за шапку (не за кнопки): место меняется, запоминается как смещение от центра
//      (ladder.cardPos) и переживает перезагрузку; сдвинули окно влево — после › текущая карточка доски встаёт
//      справа от него (там свободнее); двойной клик по шапке возвращает окно в центр. Перетаскивание окон не
//      доходит до канвы React Flow — вьюпорт доски стоит на месте (здесь, в 22b и 22c).
const boardViewport = () => page.evaluate(() => document.querySelector(".react-flow__viewport")?.style.transform ?? "");
const vpDrag0 = await boardViewport();
const c0 = await centerCard.boundingBox();
const head = await page.locator(".drawer--center .drawer__title").boundingBox();
const hx = head.x + 20;
const hy = head.y + head.height / 2;
await page.mouse.move(hx, hy);
await page.mouse.down();
await page.mouse.move(hx - 120, hy + 10, { steps: 6 });
await page.mouse.move(hx - 240, hy + 20, { steps: 6 });
await page.mouse.up();
const c1 = await centerCard.boundingBox();
if (Math.abs(c1.x - (c0.x - 240)) > 2 || Math.abs(c1.y - (c0.y + 20)) > 2) fail(`dragging the header did not move the window: ${JSON.stringify(c0)} → ${JSON.stringify(c1)}`);
if ((await boardViewport()) !== vpDrag0) fail("dragging the card window panned the board");
const cardPos = JSON.parse((await page.evaluate(() => localStorage.getItem("ladder.cardPos"))) ?? "null");
if (!cardPos || Math.abs(cardPos.dx + 240) > 2 || Math.abs(cardPos.dy - 20) > 2) fail(`window offset not stored: ${JSON.stringify(cardPos)}`);
await page.locator(".drawer__next").click();
await page.waitForTimeout(700);
const besideMoved = await besideWindow();
if (!besideMoved || besideMoved.hit || besideMoved.side !== "right") fail(`window moved left → the current card must go right of it: ${JSON.stringify(besideMoved)}`);
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector(".qnode", { timeout: 10000 });
await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().click();
await centerCard.waitFor({ timeout: 3000 });
const c2 = await centerCard.boundingBox();
if (Math.abs(c2.x - c1.x) > 1 || Math.abs(c2.y - c1.y) > 1) fail(`window position did not survive reload: ${JSON.stringify(c1)} → ${JSON.stringify(c2)}`);
await page.locator(".drawer--center .drawer__title").dblclick();
await page.waitForFunction((x) => Math.abs(document.querySelector(".drawer--center").getBoundingClientRect().x - x) <= 1, c0.x, { timeout: 3000 })
  .catch(() => fail("double click on the header did not return the window to the center"));
if ((await page.evaluate(() => localStorage.getItem("ladder.cardPos"))) !== null) fail("centered window must drop the stored offset");
console.log(`OK: card window drags by the header (${Math.round(c0.x)} → ${Math.round(c1.x)}), survives reload, current card goes right of it, double click re-centers`);

// 22b. Размер окна: уголок справа внизу тянет ширину и высоту (левый верхний угол стоит на месте), правый
//      край — только ширину; размер (ladder.cardSize) переживает перезагрузку; двойной клик по уголку — размер
//      по умолчанию min(760px, 58vw).
const vpSize0 = await boardViewport();
const s0 = await centerCard.boundingBox();
const gripBox2 = await page.locator(".drawer__grip").boundingBox();
const kx = gripBox2.x + gripBox2.width / 2;
const ky = gripBox2.y + gripBox2.height / 2;
await page.mouse.move(kx, ky);
await page.mouse.down();
await page.mouse.move(kx + 100, ky + 20, { steps: 6 });
await page.mouse.move(kx + 200, ky + 40, { steps: 6 });
await page.mouse.up();
const s1 = await centerCard.boundingBox();
if (Math.abs(s1.width - (s0.width + 200)) > 2 || Math.abs(s1.height - (s0.height + 40)) > 2) fail(`corner grip did not resize: ${JSON.stringify(s0)} → ${JSON.stringify(s1)}`);
if (Math.abs(s1.x - s0.x) > 1 || Math.abs(s1.y - s0.y) > 1) fail(`resizing moved the top-left corner: ${JSON.stringify(s0)} → ${JSON.stringify(s1)}`);
const edgeBox = await page.locator(".drawer__edge").boundingBox();
const ex = edgeBox.x + edgeBox.width / 2;
const ey = edgeBox.y + edgeBox.height / 2;
await page.mouse.move(ex, ey);
await page.mouse.down();
await page.mouse.move(ex - 50, ey, { steps: 5 });
await page.mouse.move(ex - 100, ey, { steps: 5 });
await page.mouse.up();
const s2 = await centerCard.boundingBox();
if (Math.abs(s2.width - (s1.width - 100)) > 2 || Math.abs(s2.height - s1.height) > 2) fail(`right edge must change the width only: ${JSON.stringify(s1)} → ${JSON.stringify(s2)}`);
if ((await boardViewport()) !== vpSize0) fail("resizing the card window panned the board");
const cardSize = JSON.parse((await page.evaluate(() => localStorage.getItem("ladder.cardSize"))) ?? "null");
if (!cardSize || Math.abs(cardSize.w - s2.width) > 1 || Math.abs(cardSize.h - s2.height) > 1) fail(`window size not stored: ${JSON.stringify(cardSize)}`);
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector(".qnode", { timeout: 10000 });
await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().click();
await centerCard.waitFor({ timeout: 3000 });
const s3 = await centerCard.boundingBox();
if (Math.abs(s3.width - s2.width) > 1 || Math.abs(s3.height - s2.height) > 1) fail(`window size did not survive reload: ${JSON.stringify(s2)} → ${JSON.stringify(s3)}`);
await page.locator(".drawer__grip").dblclick();
await page.waitForFunction((w) => Math.abs(document.querySelector(".drawer--center").getBoundingClientRect().width - w) <= 1, defaultCardW, { timeout: 3000 })
  .catch(() => fail("double click on the grip did not restore the default size"));
if ((await page.evaluate(() => localStorage.getItem("ladder.cardSize"))) !== null) fail("default size must drop the stored value");
await page.locator(".drawer--center .drawer__title").dblclick(); // ресайз сдвигал окно — вернуть в центр
await page.waitForFunction((x) => Math.abs(document.querySelector(".drawer--center").getBoundingClientRect().x - x) <= 1, c0.x, { timeout: 3000 })
  .catch(() => fail("window did not re-center after the size reset"));
console.log(`OK: card window resizes — grip ${Math.round(s0.width)}×${Math.round(s0.height)} → ${Math.round(s1.width)}×${Math.round(s1.height)}, edge → ${Math.round(s2.width)}, same after reload, double click → ${Math.round(defaultCardW)}`);
// «Справа»: панель как раньше — ответ сразу, без «Показать ответ» и ‹ ›; режим запомнен, ⚙ его показывает.
await page.locator(".drawer__mode").click();
const sideCard = page.locator(".drawer.drawer--side");
await sideCard.waitFor({ timeout: 3000 });
if ((await page.locator(".drawer__answer").count()) !== 1) fail("side: the answer must be visible right away");
if ((await page.locator(".drawer__prev, .drawer__next").count()) !== 0) fail("side: no ‹ › in the side panel");
if ((await page.locator(".cardscrim").count()) !== 0) fail("side: no scrim over the board");
if ((await page.evaluate(() => localStorage.getItem("ladder.cardMode"))) !== "side") fail("card mode was not stored");
await page.waitForSelector(".hud", { timeout: 3000 }); // справа HUD — как раньше
await openSettings();
if ((await page.locator('.setdrawer .cardmode__opt[data-mode="side"]').getAttribute("aria-checked")) !== "true") fail("⚙: «Справа» is not checked");
await page.keyboard.press("Escape");
await page.waitForSelector(".setdrawer", { state: "detached", timeout: 3000 });
console.log("OK: «Справа» — side panel with the answer shown, mode stored, ⚙ reflects it");
// Ручка на левом краю: тянем влево на 240px → панель шире на 240px, ширина в localStorage и после
// перезагрузки та же; двойной клик по ручке — ширина по умолчанию (460), сохранённое значение убрано.
const w0 = Math.round((await sideCard.boundingBox()).width);
if (Math.abs(w0 - 460) > 2) fail(`side panel default width must be 460, got ${w0}`);
const handleBox = await page.locator(".drawer__resize").boundingBox();
const gx = handleBox.x + handleBox.width / 2;
const gy = handleBox.y + handleBox.height / 2;
await page.mouse.move(gx, gy);
await page.mouse.down();
await page.mouse.move(gx - 120, gy, { steps: 6 });
await page.mouse.move(gx - 240, gy, { steps: 6 });
await page.mouse.up();
const w1 = Math.round((await sideCard.boundingBox()).width);
if (Math.abs(w1 - (w0 + 240)) > 3) fail(`dragging the handle did not widen the panel: ${w0} → ${w1}`);
const storedW = Number(await page.evaluate(() => localStorage.getItem("ladder.drawerWidth")));
if (Math.abs(storedW - w1) > 1) fail(`panel width not stored: ${storedW} vs ${w1}`);
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector(".qnode", { timeout: 10000 });
await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().click();
await sideCard.waitFor({ timeout: 3000 });
const w2 = Math.round((await sideCard.boundingBox()).width);
if (Math.abs(w2 - w1) > 1) fail(`panel width did not survive reload: ${w1} → ${w2}`);
await page.locator(".drawer__resize").dblclick();
await page.waitForFunction(() => Math.round(document.querySelector(".drawer--side")?.getBoundingClientRect().width ?? 0) === 460, null, { timeout: 3000 })
  .catch(() => fail("double click on the handle did not restore the default width"));
if ((await page.evaluate(() => localStorage.getItem("ladder.drawerWidth"))) !== null) fail("default width must drop the stored value");
console.log(`OK: side panel handle — ${w0} → ${w1}px, same after reload, double click → 460`);
// ⚙ «По центру» возвращает режим по умолчанию — открытая карточка переезжает в центр; дальше smoke идёт в нём.
await openSettings();
await page.locator('.setdrawer .cardmode__opt[data-mode="center"]').click();
await page.keyboard.press("Escape");
await page.waitForSelector(".setdrawer", { state: "detached", timeout: 3000 });
await page.waitForSelector(".drawer.drawer--center", { timeout: 3000 }).catch(() => fail("⚙ «По центру» did not move the open card to the center"));
if ((await page.evaluate(() => localStorage.getItem("ladder.cardMode"))) !== "center") fail("⚙: center mode was not stored");
await page.keyboard.press("Escape"); // закрыть карточку
await page.waitForSelector(".drawer", { state: "detached", timeout: 3000 });
if ((await page.locator(".cardscrim").count()) !== 0) fail("scrim must go away with the card");
console.log("OK: ⚙ «Карточка вопроса» switches the open card back to the center");

// 22c. Окно фильтров — плавающее (решение владельца 2026-09-11): по умолчанию у правого края под шапкой доски,
//      тащится за шапку (не за ✕), место (ladder.filtersPos) переживает перезагрузку, двойной клик по шапке
//      возвращает его на место.
await page.locator(".topbar .filtersbtn").click();
const fpanel = page.locator(".filterpanel");
await fpanel.waitFor({ timeout: 3000 });
const canvasBox = await page.locator(".canvas").boundingBox();
const f0 = await fpanel.boundingBox();
if (Math.abs(canvasBox.x + canvasBox.width - (f0.x + f0.width) - 15) > 2 || Math.abs(f0.y - canvasBox.y - 15) > 2) {
  fail(`filters window must start at the right edge under the board header: ${JSON.stringify(f0)} in ${JSON.stringify(canvasBox)}`);
}
await page.waitForTimeout(200); // открытие фильтров перецентровывает доску (centerBoard) — дождаться
const vpFilters0 = await boardViewport();
const fhead = await page.locator(".fp__heading").boundingBox();
const fx = fhead.x + 10;
const fy = fhead.y + fhead.height / 2;
await page.mouse.move(fx, fy);
await page.mouse.down();
await page.mouse.move(fx - 250, fy + 40, { steps: 6 });
await page.mouse.move(fx - 500, fy + 80, { steps: 6 });
await page.mouse.up();
const f1 = await fpanel.boundingBox();
if (Math.abs(f1.x - (f0.x - 500)) > 2 || Math.abs(f1.y - (f0.y + 80)) > 2) fail(`dragging the filters header did not move the window: ${JSON.stringify(f0)} → ${JSON.stringify(f1)}`);
if ((await boardViewport()) !== vpFilters0) fail("dragging the filters window panned the board");
if (!(await page.evaluate(() => localStorage.getItem("ladder.filtersPos")))) fail("filters window position was not stored");
await page.reload({ waitUntil: "networkidle" });
await fpanel.waitFor({ timeout: 10000 }); // открытость фильтров запоминается, как раньше
const f2 = await fpanel.boundingBox();
if (Math.abs(f2.x - f1.x) > 1 || Math.abs(f2.y - f1.y) > 1) fail(`filters window position did not survive reload: ${JSON.stringify(f1)} → ${JSON.stringify(f2)}`);
await page.locator(".fp__heading").dblclick();
await page.waitForFunction((x) => Math.abs(document.querySelector(".filterpanel").getBoundingClientRect().x - x) <= 1, f0.x, { timeout: 3000 })
  .catch(() => fail("double click on the filters header did not put the window back"));
if ((await page.evaluate(() => localStorage.getItem("ladder.filtersPos"))) !== null) fail("filters window back in place must drop the stored offset");
await page.locator(".fp__close").click();
await fpanel.waitFor({ state: "detached", timeout: 3000 });
console.log(`OK: filters window drags by its header (${Math.round(f0.x)} → ${Math.round(f1.x)}), survives reload, double click puts it back`);

// Работа с банком — страница #/bank/<pool> (pools-main-menu).
await page.goto(URL + "#/bank/data-engineer", { waitUntil: "load" });
await page.waitForSelector(".bankbrowser--embedded", { timeout: 10000 });

// 12. Экспорта банка нет (удалён по решению владельца 2026-09-11).
if ((await page.locator(".pageshell .bankbtn").count()) !== 0) fail("bank export button must be gone");
console.log("OK: no bank export");

// 14. Загрузка вопросов: открыть модалку, загрузить НЕвалидный .md → показана ошибка (файл не пишется).
await page.locator(".uploadbtn").click();
await page.waitForSelector(".upload-modal", { timeout: 3000 });
const badMd = "---\nid: smoke-bad-01\nblock: NOPE\ntopic: x\n---\n## Вопрос\nq\n";
await page.setInputFiles(".upload-modal input[type=file]", {
  name: "smoke-bad.md",
  mimeType: "text/markdown",
  buffer: Buffer.from(badMd),
});
await page.waitForSelector(".upload-result__err", { timeout: 3000 });
const upErr = await page.locator(".upload-result__err").innerText();
if (!upErr.toLowerCase().includes("ошибк")) fail(`upload error not shown: "${upErr}"`);
console.log("OK: upload rejects invalid file with error");
await page.keyboard.press("Escape");
await page.waitForSelector(".upload-modal", { state: "detached", timeout: 3000 });

// 16. Банк вопросов на странице #/bank/<pool> (bank-browser встроен, экран открыт по умолчанию):
// список всего банка, поиск, раскрытие. Страница не закрывается — Esc/закрытие не проверяем.
const bankRows = await page.locator(".bankrow").count();
if (bankRows < nodeCount) fail(`bank shows fewer rows (${bankRows}) than canvas nodes (${nodeCount})`);
console.log(`OK: bank screen lists ${bankRows} questions`);
await page.locator(".bankbrowser__search").fill("ROW_NUMBER");
await page.waitForTimeout(250);
const bankFiltered = await page.locator(".bankrow").count();
if (bankFiltered < 1 || bankFiltered >= bankRows) fail(`bank search did not narrow rows (${bankRows} → ${bankFiltered})`);
console.log(`OK: bank search narrows ${bankRows} → ${bankFiltered}`);
await page.locator(".bankrow__head").first().click();
await page.waitForSelector(".bankrow--open .bankrow__body", { timeout: 3000 });
const bodyLen = (await page.locator(".bankrow--open .bankrow__body").first().innerText()).length;
if (bodyLen < 30) fail(`expanded bank row body too short (${bodyLen})`);
console.log("OK: bank row expands with question/answer/criteria");
await page.locator(".bankbrowser__search").fill(""); // сброс — иначе шаг 18 не увидит новую строку
await page.waitForTimeout(200);

// 18. question-management: добавить вопрос через форму банка → банк растёт (бэкенд пишет в БД).
const rowsBeforeAdd = await page.locator(".bankrow").count();
await page.locator(".addbtn").click();
await page.waitForSelector(".addform", { timeout: 3000 });
await page.locator(".addform input[placeholder^='например']").fill("smoke-add-topic"); // поле «Тема» (обязательное)
await page.locator(".addform textarea").first().fill("Smoke вопрос-добавление?");
const [addResp] = await Promise.all([
  page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith("/api/nodes")),
  page.locator(".addform__btns button", { hasText: "Создать" }).click(),
]);
const addedId = (await addResp.json()).id;
await page.waitForTimeout(700);
const rowsAfterAdd = await page.locator(".bankrow").count();
if (rowsAfterAdd !== rowsBeforeAdd + 1) fail(`add-question did not grow the bank by one (${rowsBeforeAdd}→${rowsAfterAdd})`);
console.log(`OK: add question grows bank (${rowsBeforeAdd}→${rowsAfterAdd})`);
// Уборка: без явного subblock (форма его не задаёт) вопрос заводит собственную под-колонку —
// повторные прогоны smoke на том же контейнере иначе бесконечно раздвигают доску. Удаляем тем же
// API, что уже проверен «.drawer__delete»-шагом (20); id берём из ответа POST, а не хардкодим.
await page.request.delete(URL + `api/nodes/${addedId}`);

// Возврат на доску направления.
await page.goto(URL + "#/board/data-engineer", { waitUntil: "load" });
await page.waitForSelector(".qnode", { timeout: 10000 });

// 19. question-management: открыть вопрос → drawer; правка (открыть/Отмена) неразрушающа.
// Доска смонтирована заново (после банка) на дефолтном зуме: панель фильтров может накрыть
// карточку, поэтому сначала закрываем её, а потом кликаем по самой карточке.
await closeFiltersIfOpen();
await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().click();
await page.waitForSelector(".drawer__edit", { timeout: 3000 });
await page.locator(".drawer__edit").click();
await page.waitForSelector(".drawer__editform", { timeout: 3000 });
await page.locator(".drawer__editform textarea").first().fill("ЧЕРНОВИК — НЕ СОХРАНЯЕМ");
await page.locator(".drawer__editbtns button", { hasText: "Отмена" }).click();
await page.waitForTimeout(200);
if ((await page.locator(".drawer__editform").count()) !== 0) fail("edit form still open after cancel");
console.log("OK: edit mode opens + cancel is non-destructive");

// hide-local: «Скрыть» гасит карточку; тумблер «Скрытые» помечает её (.qnode--hidden).
const dimBeforeHide = await page.locator(".qnode--dimmed").count();
await page.locator(".drawer__hide").click();
await page.waitForTimeout(250);
const dimAfterHide = await page.locator(".qnode--dimmed").count();
if (dimAfterHide <= dimBeforeHide) fail(`hide did not dim node (${dimBeforeHide}→${dimAfterHide})`);
await toggleSetting("Скрытые");
await page.waitForTimeout(250);
const hiddenMark = await page.locator(".qnode--hidden").count();
if (hiddenMark < 1) fail("no .qnode--hidden marker after show-hidden");
await toggleSetting("Скрытые"); // спрятать обратно
await page.locator(".drawer__hide").click(); // вернуть карточку на доску
await page.waitForTimeout(150);
console.log(`OK: hide dims (${dimBeforeHide}→${dimAfterHide}), show-hidden marks (${hiddenMark})`);

// 20. question-management: удаление — confirm всплывает; dismiss НЕ меняет банк.
let confirmFired = false;
// Именованный и снимается после проверки: иначе он «отклоняет» и все следующие confirm (шаг 26).
const dismissDialog = (d) => { confirmFired = true; d.dismiss(); };
page.on("dialog", dismissDialog);
const qBeforeDel = await page.locator(".qnode").count();
await page.locator(".drawer__delete").click();
await page.waitForTimeout(250);
page.off("dialog", dismissDialog);
if (!confirmFired) fail("delete did not raise a confirm dialog");
if ((await page.locator(".qnode").count()) !== qBeforeDel) fail("dismissed delete changed bank");
console.log(`OK: delete confirms + dismiss non-destructive (${qBeforeDel} nodes)`);

// 21. Персистентность чек-листа: статус живёт в БД через /api/progress, не в localStorage —
// поставить «повторить» через HUD, пережить page.reload() (ПОСЛЕДНЕЙ), затем снять тем же кликом.
await page.waitForSelector(".qnode", { timeout: 10000 });
await page.keyboard.press("Escape"); // закрыть drawer
await closeFiltersIfOpen();
await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().click();
// Карточка открылась по центру — HUD на это время скрыт; Esc закрывает её, курсор остаётся на ROW_NUMBER.
await page.waitForSelector(".drawer", { timeout: 3000 });
await page.keyboard.press("Escape");
await page.waitForSelector(".hud__score .statusbtn--review", { timeout: 3000 });
await page.locator(".hud__score .statusbtn--review").click(); // «повторить»
await page.waitForSelector('.qnode__status[data-status="review"]', { timeout: 3000 });
if ((await rowNumberCard.locator('.qnode__status[data-status="review"]').count()) !== 1) fail("HUD review status not applied to ROW_NUMBER");
// page.reload() (не goto) — держит текущий hash (#/board/data-engineer), иначе после «goto на тот же
// URL» браузер не обязан перезагружать документ и тест не проверит persistence по-настоящему.
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector(".qnode", { timeout: 10000 });
await page.waitForSelector('.qnode__status[data-status="review"]', { timeout: 10000 }).catch(() => fail("checklist status did not survive reload"));
if ((await rowNumberCard.locator('.qnode__status[data-status="review"]').count()) !== 1) fail("checklist status not on ROW_NUMBER after reload");
console.log("OK: checklist status survives reload (review)");
// снять статус обратно (повтор той же кнопки) — не портим финальное состояние стенда.
await closeFiltersIfOpen();
await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().click();
await page.waitForSelector(".drawer", { timeout: 3000 });
await page.keyboard.press("Escape"); // карточка по центру прячет HUD — закрываем её
await page.waitForSelector(".hud__score .statusbtn--review", { timeout: 3000 });
await page.locator(".hud__score .statusbtn--review").click();
await rowNumberCard
  .locator('.qnode__status[data-status="review"]')
  .waitFor({ state: "detached", timeout: 3000 })
  .catch(() => fail("repeat click on HUD status button did not clear the checklist status"));
console.log("OK: checklist status cleared");

// 24. Неизвестный пул в адресе → меню с пометкой, без падения.
await page.goto(URL + "#/board/nope", { waitUntil: "load" });
await page.waitForSelector(".poolcard", { timeout: 10000 });
if ((await page.locator(".errbar").count()) !== 1) fail("unknown pool should show a notice on the menu");
console.log("OK: unknown pool falls back to menu");

// 25. Другой пул рисует СВОИ колонки: system-analyst (второй пресет в репозитории).
// Регистронезависимо: оформление 37 и тёмная тема переводят .bgroup__header в uppercase CSS'ом.
for (const [pid, needle] of [["system-analyst", "требования"]]) {
  await page.goto(URL + "#/", { waitUntil: "load" });
  await page.waitForSelector(`.poolcard[data-pool="${pid}"]`, { timeout: 10000 });
  await page.goto(URL + `#/board/${pid}`, { waitUntil: "load" });
  await page.waitForSelector(".bgroup__header", { timeout: 10000 });
  const heads = await page.locator(".bgroup__header").allInnerTexts();
  if (!heads.some((h) => h.toLowerCase().includes(needle))) fail(`${pid} board lacks its own blocks: ${heads.join(" | ")}`);
  console.log(`OK: ${pid} board has its own blocks (${heads.length})`);
}

// 26. Аккаунты (spec 2026-09-11): owner заводит viewer'а на «Люди» (одноразовый пароль показан один
//     раз) → выход → вход viewer'ом: все направления, без правки, свой чек-лист на сервере, смена пароля.
await page.goto(URL + "#/people", { waitUntil: "networkidle" });
const viewerEmail = `viewer-${Date.now()}@smoke.test`;
await page.fill(".people__email", viewerEmail);
await page.click(".people__submit");
await page.waitForSelector(".people__password", { timeout: 5000 });
const viewerPw = (await page.locator(".people__password").innerText()).trim();
if (viewerPw.length < 12) fail("people: одноразовый пароль не показан");
console.log("OK: people — account created with a one-time password");
await page.goto(URL, { waitUntil: "networkidle" });
await page.click(".account__btn");
await page.click(".account__logout");
await page.waitForSelector(".landing__demo", { timeout: 10000 });
await page.goto(URL + "#/login", { waitUntil: "networkidle" });
await page.fill('.login__input[type="email"]', viewerEmail);
await page.fill('.login__input[type="password"]', viewerPw);
await page.click(".login__card button[type=submit]");
await page.waitForSelector('.poolcard[data-pool="system-analyst"]', { timeout: 10000 });
if ((await page.locator(".home__add, .poolcard__menu").count()) !== 0) fail("viewer: видна правка направлений");
await page.click(".account__btn");
if ((await page.locator(".account__people").count()) !== 0) fail("viewer: в меню аккаунта есть «Люди»");
await page.click(".account__password");
await page.fill(".pwmodal__current", viewerPw);
await page.fill(".pwmodal__new", "viewer-new-pass-1");
await page.fill(".pwmodal__repeat", "viewer-new-pass-1");
await page.click(".pwmodal__submit");
await page.waitForSelector(".pwmodal__ok", { timeout: 5000 }).catch(() => fail("viewer: пароль не сменился"));
console.log("OK: viewer signs in, sees all pools read-only, changes the password");
// Доска viewer'а: карточку открываем с клавиатуры (↓ — первая карточка матрицы, Enter — drawer),
// правки в drawer нет, «1» пишет статус на сервер (чек-лист у любой роли).
await page.goto(URL + "#/board/system-analyst", { waitUntil: "networkidle" });
await page.waitForSelector(".react-flow__node-question", { timeout: 15000 });
await page.keyboard.press("ArrowDown");
await page.keyboard.press("Enter");
await page.waitForSelector(".drawer", { timeout: 5000 });
if ((await page.locator(".drawer__delete, .drawer__edit").count()) !== 0) fail("viewer: в drawer есть удаление/правка");
const [viewerProgress] = await Promise.all([
  page.waitForResponse((r) => r.request().method() === "PUT" && r.url().includes("/api/progress/")),
  page.keyboard.press("1"),
]);
if (viewerProgress.status() !== 200) fail(`viewer: статус чек-листа не сохранён (${viewerProgress.status()})`);
console.log("OK: viewer board — no editing, checklist saved on the server");
// Уборка: owner удаляет viewer'а (confirm называет почту) — повторные прогоны на том же стенде без мусора.
await page.goto(URL + "#/", { waitUntil: "networkidle" });
await page.click(".account__btn");
await page.click(".account__logout");
await page.waitForSelector(".landing__demo", { timeout: 10000 });
await page.goto(URL + "#/login", { waitUntil: "networkidle" });
await page.fill('.login__input[type="email"]', OWNER_EMAIL);
await page.fill('.login__input[type="password"]', OWNER_PASSWORD);
await page.click(".login__card button[type=submit]");
await page.waitForSelector(".account__btn", { timeout: 10000 });
await page.goto(URL + "#/people", { waitUntil: "networkidle" });
const viewerRow = page.locator(`.people__table tr[data-email="${viewerEmail}"]`);
await viewerRow.waitFor({ timeout: 5000 });
let accountConfirm = "";
page.once("dialog", (d) => { accountConfirm = d.message(); d.accept(); });
await viewerRow.locator(".people__delete").click();
await viewerRow.waitFor({ state: "detached", timeout: 5000 }).catch(() => fail("people: аккаунт не удалён"));
if (!accountConfirm.includes(viewerEmail)) fail(`people: confirm не называет почту: "${accountConfirm}"`);
console.log("OK: people — owner deletes the account (confirm names the email)");

const lateErrors = unexpectedErrors();
if (lateErrors.length) fail(`console/page errors:\n${lateErrors.join("\n")}`);

// 27. Регрессия флака CI (2026-09-11): фоновые узлы доски — полосы уровней, колонки, подзаголовки —
//     не должны зависеть от замера ResizeObserver. Когда замер терялся, они оставались hidden навсегда
//     (`.bgroup__header` «not visible»), а карточки вопросов с явным размером — нет.
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => {
    window.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  });
  const p2 = await ctx.newPage();
  await p2.goto(URL + "#/board/data-engineer", { waitUntil: "networkidle" });
  await p2.waitForSelector(".react-flow__node-blockGroup", { state: "attached", timeout: 15000 });
  const hiddenStatic = await p2.evaluate(
    () => [...document.querySelectorAll(".react-flow__node-bands, .react-flow__node-blockGroup, .react-flow__node-subhead")]
      .filter((n) => n.style.visibility === "hidden").length,
  );
  if (hiddenStatic !== 0) fail(`board: ${hiddenStatic} static nodes stay hidden without a ResizeObserver measurement`);
  if (!(await p2.locator(".bgroup__header").first().isVisible())) fail("board: column headers not visible without a ResizeObserver measurement");
  await ctx.close();
  console.log("OK: board columns render without a ResizeObserver measurement (static nodes carry their size)");
}

console.log("\nALL SMOKE CHECKS PASSED ✓");
await browser.close();
