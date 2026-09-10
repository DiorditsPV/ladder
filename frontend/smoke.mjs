// Headless smoke-тест реального рантайма (доска рендерится, карточка → drawer, чек-лист, банк).
// Запуск: node smoke.mjs   (сервер должен слушать http://localhost:8000)
import { chromium } from "playwright";

const URL = process.env.SMOKE_URL || "http://localhost:8000/";
const fail = (m) => { console.error("FAIL:", m); process.exit(1); };

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

// topbar-settings: тумблеры отображения — в боковой панели (.setdrawer) под ⚙, а ⚙ (.setbtn) —
// пункт меню «•••» toolbar'а (board-toolbar). Каждое переключение = ••• → Настройки → чип → Esc.
// Пункт меню закрывает «•••» сам; Esc закрывает панель (перехватывается в capture-фазе внутри
// SettingsMenu), поэтому дожидаемся её исчезновения перед следующим шагом.
async function openSettings() {
  await page.locator(".morebtn").click();
  await page.waitForSelector(".moremenu", { timeout: 3000 });
  await page.locator(".moremenu .setbtn").click();
  await page.waitForSelector(".setdrawer", { timeout: 3000 });
  await page.waitForSelector(".moremenu", { state: "detached", timeout: 3000 });
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

await page.goto(URL, { waitUntil: "networkidle" });

// 0. auth-identity (#36): доска за гейтом — логинимся owner'ом (дефолтные сид-креды).
await page.waitForSelector(".login__card", { timeout: 10000 });
await page.fill('.login__input[type="email"]', process.env.SMOKE_OWNER_EMAIL || "owner@interview.local");
await page.fill('.login__input[type="password"]', process.env.SMOKE_OWNER_PASSWORD || "interview-dev");
await page.click(".login__card button[type=submit]");
console.log("OK: logged in as owner");
// AuthGate проверяет сессию через /api/auth/me ДО логина → ожидаемый 401 в консоли.
// Сбрасываем накопленное, чтобы он не считался ошибкой; пост-логин запросы идут с cookie.
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

// 3. Клик по ноде с УСЛОВНЫМ ребром (sql-01 → conditional → sql-02) открывает drawer.
await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().click();
await page.waitForSelector(".drawer", { timeout: 5000 });
const drawerText = await page.locator(".drawer__body").innerText();
if (drawerText.length < 50) fail("drawer body too short");
console.log("OK: drawer opened with content");

// 3b. Клик задаёт «текущую карточку» → появляется HUD.
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
await page.locator(".qnode__title", { hasText: "KubernetesExecutor" }).first().click();
await page.waitForSelector(".hud", { timeout: 3000 });
const beforeNext = await page.locator(".hud__title").innerText();
await page.keyboard.press("n");
await page.waitForTimeout(500);
const afterNext = await page.locator(".hud__title").innerText();
if (afterNext === beforeNext) fail("«n» stuck on the current card");
console.log("OK: «n» advances to the next unreviewed card");

// 6b. Настройки отображения (topbar-settings): панель под ⚙ (пункт «•••») открывается и содержит
// тумблеры направляющих, точек-фона, скрытых и таймера.
await openSettings();
const tbBtns = await page.locator(".setdrawer .tb__toggle").count();
if (tbBtns < 6) fail(`display toggles missing in settings drawer (got ${tbBtns})`);
await page.keyboard.press("Escape");
await page.waitForSelector(".setdrawer", { state: "detached", timeout: 3000 });
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

// 7. Экспорт: в меню toolbar'а остался ровно один пункт — банк вопросов (отчёта по сессии нет).
await page.locator(".topbar .exportbtn").click();
await page.waitForSelector(".exportmenu", { timeout: 3000 });
if ((await page.locator(".exportmenu .tbmenu__item").count()) !== 1) fail("export menu must offer exactly one item (question bank)");
if ((await page.locator(".exportmenu .bankbtn").count()) !== 1) fail("bank export item missing");
await page.keyboard.press("Escape");
await page.waitForSelector(".exportmenu", { state: "detached", timeout: 3000 });
console.log("OK: export menu offers the question bank only");

// 8. Тёмная тема: переключатель в настройках меняет data-theme и тёмный фон.
const before = await page.evaluate(() => document.documentElement.dataset.theme || "light");
await openSettings();
await page.locator(".setdrawer .themebtn").click();
await page.keyboard.press("Escape");
await page.waitForTimeout(200);
const after = await page.evaluate(() => document.documentElement.dataset.theme);
if (after === before) fail(`theme toggle did not change theme (${before} → ${after})`);
console.log(`OK: theme toggles (${before} → ${after})`);

// --- Накопленные проверки фич. Порядок важен: локально-стейтовые (таймер/поиск/чек-лист)
//  идут до шага 21, который делает page.reload() и стирает накопленное состояние.

// 9b. Таймер разбора: по умолчанию скрыт (topbar-settings), включается тумблером в ⚙ — и тикает.
await page.keyboard.press("Escape"); // закрыть drawer, если открыт с предыдущих шагов
await page.waitForTimeout(150);
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

// 17. board-toolbar: шапка — один ряд: «← Направления», название, фильтры, экспорт, RU/EN, •••;
//     прогресса нет; ⚙ — пункт меню •••; кнопок банка/темы в шапке нет.
const topRows = await page.locator(".topbar > .topbar__row").count();
if (topRows !== 1) fail(`expected exactly 1 topbar row, got ${topRows}`);
if ((await page.locator(".topbar .topbar__back").count()) !== 1) fail("back-to-menu link missing");
if (!(await page.locator(".topbar .appname").innerText()).includes("Дата-инженер")) fail("pool label missing in topbar");
for (const sel of [".filtersbtn", ".exportbtn", ".langswitch", ".morebtn"]) {
  if ((await page.locator(`.topbar ${sel}`).count()) !== 1) fail(`toolbar element ${sel} missing`);
}
if ((await page.locator(".topbar .progress").count()) !== 0) fail("progress bar must not be in the toolbar");
if ((await page.locator(".topbar .setbtn").count()) !== 0) fail("settings must live inside the ••• menu, not in the toolbar");
if ((await page.locator(".topbar .addbtn, .topbar .bankbtn, .topbar .themebtn").count()) !== 0) fail("bank/theme buttons must leave the topbar");
await page.locator(".topbar .morebtn").click();
await page.waitForSelector(".moremenu", { timeout: 3000 });
if ((await page.locator(".moremenu .setbtn").count()) !== 1) fail("settings item missing in ••• menu");
if ((await page.locator(".moremenu .helpbtn").count()) !== 1) fail("shortcuts item missing in ••• menu");
if (!(await page.locator(".moremenu .bankLink").getAttribute("href"))?.startsWith("#/bank/data-engineer")) fail("••• menu must link to the question bank");
await page.keyboard.press("Escape");
await page.waitForSelector(".moremenu", { state: "detached", timeout: 3000 });
console.log(`OK: board toolbar (${topRows} row, back link, pool label, filters/export/•••)`);

// Работа с банком — страница #/bank/<pool> (pools-main-menu).
await page.goto(URL + "#/bank/data-engineer", { waitUntil: "load" });
await page.waitForSelector(".bankbrowser--embedded", { timeout: 10000 });

// 12. Экспорт банка вопросов: кнопка отдаёт ladder_bank_*.html (всегда активна, без reload).
const [dlBank] = await Promise.all([
  page.waitForEvent("download"),
  page.locator(".pageshell .bankbtn").click(),
]);
const bankFn = dlBank.suggestedFilename();
if (!bankFn.includes("bank") || !bankFn.endsWith(".html")) fail(`bank export wrong file: ${bankFn}`);
console.log(`OK: question bank export (${bankFn})`);

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
page.on("dialog", (d) => { confirmFired = true; d.dismiss(); });
const qBeforeDel = await page.locator(".qnode").count();
await page.locator(".drawer__delete").click();
await page.waitForTimeout(250);
if (!confirmFired) fail("delete did not raise a confirm dialog");
if ((await page.locator(".qnode").count()) !== qBeforeDel) fail("dismissed delete changed bank");
console.log(`OK: delete confirms + dismiss non-destructive (${qBeforeDel} nodes)`);

// 21. Персистентность чек-листа: статус живёт в БД через /api/progress, не в localStorage —
// поставить «повторить» через HUD, пережить page.reload() (ПОСЛЕДНЕЙ), затем снять тем же кликом.
await page.waitForSelector(".qnode", { timeout: 10000 });
await page.keyboard.press("Escape"); // закрыть drawer
await closeFiltersIfOpen();
await page.locator(".qnode__title", { hasText: "ROW_NUMBER" }).first().click();
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

// 25. Другие пулы рисуют СВОИ колонки: system-analyst и data-engineer-x5 (независимые пулы).
// Регистронезависимо: дефолтный дизайн 37 переводит .bgroup__header в uppercase CSS'ом.
for (const [pid, needle] of [["system-analyst", "требования"], ["data-engineer-x5", "python"]]) {
  await page.goto(URL + "#/", { waitUntil: "load" });
  await page.waitForSelector(`.poolcard[data-pool="${pid}"]`, { timeout: 10000 });
  await page.goto(URL + `#/board/${pid}`, { waitUntil: "load" });
  await page.waitForSelector(".bgroup__header", { timeout: 10000 });
  const heads = await page.locator(".bgroup__header").allInnerTexts();
  if (!heads.some((h) => h.toLowerCase().includes(needle))) fail(`${pid} board lacks its own blocks: ${heads.join(" | ")}`);
  console.log(`OK: ${pid} board has its own blocks (${heads.length})`);
}

if (errors.length) fail(`console/page errors:\n${errors.join("\n")}`);

console.log("\nALL SMOKE CHECKS PASSED ✓");
await browser.close();
