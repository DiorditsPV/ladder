// Словарь RU → EN интерфейса. Ключ — русская строка ровно как в коде (см. i18n.tsx):
// изменил фразу в коде — измени ключ здесь, иначе перевод молча потеряется.
// Группы — по файлам; подстановки вида {name} сохраняются как есть.
// Ключ, встречающийся в нескольких файлах, лежит в группе «Общие» (в литерале объекта
// один ключ может быть только один раз).
export const EN: Record<string, string> = {
  // --- LevelsEditor / PoolFormModal: уровни направления ---
  "Уровни — ряды матрицы сверху вниз: первый в списке самый лёгкий и рисуется верхним рядом. От 2 до 8.": "Levels are the matrix rows, top to bottom: the first one is the easiest and is drawn as the top row. From 2 to 8.",
  "Название уровня": "Level name",
  "Удалить уровень «{label}» и его вопросы ({n})?": "Delete level “{label}” and its questions ({n})?",
  "Убрать уровень": "Remove level",
  "+ Добавить уровень": "+ Add level",
  // --- HomePage: «Обновить из файлов» ---
  "Обновить из файлов": "Reload from files",
  "Обновлено из файлов: направлений {p}, вопросов {n}, скрыто {h}, конфликтов {c}": "Reloaded from files: {p} pools, {n} questions, {h} hidden, {c} conflicts",
  "Ошибок импорта: {n}; первая — {file}: {error}": "Import errors: {n}; first — {file}: {error}",
  "Не удалось обновить из файлов": "Could not reload from files",
  "Отмена": "Cancel",
  "Сохранить": "Save",
  "Создать": "Create",
  "Открыть": "Open",
  "Закрыть (Esc)": "Close (Esc)",
  "Загрузка…": "Loading…",
  "вопрос": "question",
  "задача": "task",
  "Вопрос": "Question",
  "Задача": "Task",
  "Ответ": "Answer",
  "Эталон / решение": "Reference solution",
  "Заголовок": "Title",
  "Сложность": "Difficulty",
  "Тип": "Type",
  "Стартовый код": "Starter code",
  "Критерии самопроверки": "Self-check criteria",
  "Банк вопросов": "Question bank",
  "Горячие клавиши": "Keyboard shortcuts",
  "Настройки": "Settings",
  "Направления": "Tracks",
  "Открыть вопросы": "Open questions",


  // --- HomePage ---
  "Ladder · разбор тем по ступеням": "Ladder · topics by rungs",
  "Открыть доску": "Open the board",
  "+ Новое направление": "+ New track",
  "Меню направления": "Track menu",
  "Нет ни одного направления: создайте первое кнопкой «+ Новое направление» или положите каталог с `pool.yaml` в `content/`.":
    "No tracks yet: create the first one with “+ New track” or put a directory with `pool.yaml` into `content/`.",
  "Не удалось удалить направление": "Could not delete track",
  "Дублировать": "Duplicate",
  "{label} (копия)": "{label} (copy)",
  "Не удалось дублировать направление": "Could not duplicate track",

  // --- PageShell / LangSwitch ---
  "← Меню": "← Menu",
  "Главное меню": "Main menu",
  "Русский": "Russian",
  "English": "English",

  // --- Router ---
  "Не удалось загрузить направления: {error}": "Could not load tracks: {error}",
  "Направления «{pool}» нет": "No track “{pool}”",

  // --- Login ---
  "Вход": "Sign in",
  "пароль": "password",
  "Войти": "Sign in",
  "Неверный email или пароль": "Invalid email or password",

  // --- BoardPage ---
  "Ещё": "More",
  "Шпаргалка клавиш": "Keyboard cheat sheet",
  "⚠ Ошибки импорта ({n}):": "⚠ Import errors ({n}):",
  "Загрузка графа…": "Loading board…",
  "Фильтры вопросов": "Question filters",
  "Фильтры": "Filters",
  "Фильтры активны": "Filters active",
  "Закрыть фильтры": "Close filters",
  "Потяните за шапку, чтобы переместить окно; двойной клик — вернуть на место": "Drag the header to move the window; double-click to put it back",
  "Поиск по вопросам…": "Search questions…",
  "Поиск по вопросам": "Search questions",
  "Блоки": "Blocks",
  "Прогресс": "Progress",
  "Теги": "Tags",
  "сбросить": "reset",
  "Снять выбор (Esc)": "Clear selection (Esc)",
  "Не удалось удалить вопрос": "Could not delete question",
  "Не удалось сохранить изменения": "Could not save changes",

  // --- BankPage ---
  "Добавить вопрос": "Add question",
  "Загрузить файл": "Upload file",




  // --- AddQuestionModal ---
  "Не удалось создать вопрос": "Could not create question",
  "Новый вопрос": "New question",
  "Блок": "Block",
  "Тема": "Topic",
  "например, sql": "e.g. sql",
  "Теги (через запятую)": "Tags (comma-separated)",

  // --- PoolFormModal (мастер направления) ---
  "Не удалось создать направление": "Could not create track",
  "Не удалось сохранить направление": "Could not save track",
  "Направление создано, но структуру сохранить не удалось": "Track created, but its structure could not be saved",
  "Новое направление": "New track",
  "Направление · {label}": "Track · {label}",
  "Название": "Name",
  "Описание": "Description",
  "Набор вопросов": "Question set",
  "Без пресета — создать самостоятельно": "No preset — build from scratch",
  "С пресетом копируются его разделы и вопросы; структуру можно поправить на следующем шаге.":
    "A preset copies its sections and questions; the structure can be adjusted on the next step.",
  "Разделы — колонки матрицы вопросов, подкатегории — под-колонки внутри раздела. Порядок меняется перетаскиванием за ⠿.":
    "Sections are the columns of the question matrix, subcategories are sub-columns inside a section. Reorder by dragging ⠿.",
  "Шаг {n} из {total}": "Step {n} of {total}",
  "Основное": "Basics",
  "Структура вопросов": "Question structure",
  "Структура": "Structure",
  "Проверка": "Review",
  "Далее →": "Next →",
  "← Назад": "← Back",

  // --- BlocksEditor (структурный редактор: раздел → подкатегории) ---
  "Цвет раздела": "Section color",
  "Название раздела": "Section name",
  "Название подкатегории": "Subcategory name",
  "Меню раздела": "Section menu",
  "Перетащите, чтобы изменить порядок": "Drag to reorder",
  "Вверх": "Up",
  "Вниз": "Down",
  "Удалить раздел": "Delete section",
  "Удалить раздел «{label}» и его вопросы ({n})?": "Delete section “{label}” and its questions ({n})?",
  "Убрать подкатегорию": "Remove subcategory",
  "+ Добавить подкатегорию": "+ Add subcategory",
  "+ Добавить раздел": "+ Add section",

  "Уровни": "Levels",

  // --- UploadModal ---
  "Загрузить вопросы": "Upload questions",
  "Перетащите .md / .json сюда или нажмите для выбора": "Drop .md / .json here or click to choose",
  "Добавлено: {n}": "Added: {n}",
  "Ошибки: {n}": "Errors: {n}",

  // --- SettingsMenu ---
  "Оформление": "Look",
  "Оформление доски": "Board look",
  "Тёмная тема": "Dark theme",
  "Светлая тема": "Light theme",
  "Холст": "Canvas",
  "Отображение холста": "Canvas display",
  "Точки на фоне": "Background dots",
  "Границы блоков": "Block boundaries",
  "Вертикальные направляющие": "Vertical guides",
  "Ряды уровней направления": "The direction's level rows",
  "Горизонтальные направляющие": "Horizontal guides",
  "Панели": "Panels",
  "Показывать вопросы, убранные с доски": "Show questions removed from the board",
  "Скрытые вопросы": "Hidden questions",
  "Таймер": "Timer",
  "Открыть банк направления →": "Open the track's question bank →",
  "Справка": "Help",


  // --- DetailDrawer ---
  "Детали вопроса": "Question details",
  "🛠 задача": "🛠 task",
  "❓ вопрос": "❓ question",
  "Вернуть на доску": "Return to board",
  "Скрыть с доски (локально, обратимо)": "Hide from board (local, reversible)",
  "Вернуть": "Return",
  "Скрыть": "Hide",
  "Удалить вопрос «{name}» из банка безвозвратно?": "Delete question “{name}” from the bank permanently?",
  "Удалить вопрос из банка (необратимо)": "Delete question from the bank (irreversible)",
  "Удалить": "Delete",
  "Редактировать вопрос (в банке)": "Edit question (in the bank)",
  "Редактировать": "Edit",
  "Развернуть/свернуть": "Expand/collapse",
  "Свернуть": "Collapse",
  "На весь экран": "Full screen",
  "💾 Сохранить": "💾 Save",
  "Предыдущая карточка": "Previous card",
  "Следующая карточка": "Next card",
  "Потяните, чтобы изменить ширину; двойной клик — ширина по умолчанию": "Drag to change the width; double-click for the default width",
  // --- окно карточки по центру: перетаскивание за шапку и ручки размера ---
  "Потяните за шапку, чтобы переместить окно; двойной клик — вернуть в центр": "Drag the header to move the window; double-click to re-center it",
  "Потяните, чтобы изменить размер; двойной клик — размер по умолчанию": "Drag to resize; double-click for the default size",
  "Потяните, чтобы изменить ширину; двойной клик — размер по умолчанию": "Drag to change the width; double-click for the default size",
  // --- режим карточки: DetailDrawer (кнопка в шапке) + SettingsMenu (чипы в ⚙) ---
  "Карточка вопроса": "Question card",
  "По центру": "Center",
  "Справа": "Side",
  "Показывать карточку по центру доски": "Show the card in the middle of the board",
  "Показывать карточку в панели справа": "Show the card in a panel on the right",

  // --- BankBrowser ---
  "Все вопросы": "All questions",
  "показано {shown} из {total}": "showing {shown} of {total}",
  "Поиск по тексту, теме, тегам…": "Search text, topic, tags…",
  "Развернуть всё": "Expand all",
  "Свернуть всё": "Collapse all",
  "Ничего не найдено": "Nothing found",
  "Всё разобрано": "All done",
  "Показать все": "Show all",
  "В направлении пока нет вопросов": "This direction has no questions yet",

  // --- QuestionNode ---
  "скрыт · ": "hidden · ",

  // --- report.ts ---
  "Сгенерировано локальным сервисом «Ladder»": "Generated by the local Ladder service",
  "Заготовка кода": "Starter code",
  "Критерии": "Criteria",
  "Банк пуст.": "The bank is empty.",

  // --- study-progress: чек-лист разбора (статусы вне сессии) ---
  "Знаю (1)": "Know it (1)",
  "Повторить (2)": "Revisit (2)",
  "Не знаю (3)": "Don't know (3)",
  "Только неразобранное": "Unresolved only",
  "знаю {k} из {n}": "{k} of {n} known",
  "Разобрано": "Reviewed",
  "Знаю": "Known",
  // --- ShortcutsHelp: подписи приходят через t(desc), i18n-check их не видит ---
  "знаю · повторить · не знаю": "known · review · don't know",
  "открыть карточку текущего вопроса": "open the current question's card",
  "перейти к следующему неразобранному": "go to the next unreviewed question",
  "навигация по сетке вопросов": "navigate the question grid",
  "снять выделение / закрыть эту шпаргалку": "clear selection / close this cheat sheet",
  "показать / скрыть эту шпаргалку": "show / hide this cheat sheet",
  "Удалить направление «{label}»? Вопросы ({nodes}) будут удалены безвозвратно.":
    "Delete direction “{label}”? Its questions ({nodes}) will be deleted permanently.",
  "Время на карточку · весь разбор": "Time per card · total study time",
  "Время на карточку и на весь разбор в нижней панели": "Time per card and total study time in the bottom bar",

  // --- Landing: стартовый экран демо-режима (spec 2026-09-11) ---
  "Тема разложена на колонки и ступени. Проходите карточки и отмечайте: знаю, повторить, не знаю.":
    "Each topic is laid out in columns and rungs. Work through the cards and mark each one: know it, revisit, don't know.",
  "Открыть демо": "Open demo",
  "Дата-инженер и системный аналитик — на русском и английском.": "Data engineer and system analyst — in Russian and English.",

  // --- AccountMenu / SettingsMenu / ChangePasswordModal: аккаунт полного режима ---
  "Сменить пароль": "Change password",
  "Люди": "People",
  "Выйти": "Sign out",
  "Аккаунт": "Account",
  "Текущий пароль": "Current password",
  "Новый пароль": "New password",
  "Повторите новый пароль": "Repeat new password",
  "Сменить": "Change",
  "Новый пароль — не короче 8 символов": "The new password must be at least 8 characters",
  "Пароли не совпадают": "Passwords do not match",
  "Текущий пароль неверный": "The current password is wrong",
  "Не удалось сменить пароль": "Could not change the password",
  "Пароль изменён. Остальные устройства вышли из аккаунта.": "Password changed. Other devices have been signed out.",

  // --- PeoplePage ---
  "Добавить": "Add",
  "Пароль для {email} — показывается один раз:": "Password for {email} — shown only once:",
  "Скопировать": "Copy",
  "Почта": "Email",
  "Доступ": "Access",
  "Заведён": "Added",
  "Сбросить пароль": "Reset password",
  "Удалить аккаунт {email} вместе с его чек-листом?": "Delete the account {email} together with its checklist?",
  "Такой аккаунт уже есть": "This account already exists",
  "Не удалось добавить": "Could not add",
  "Не удалось сбросить пароль": "Could not reset the password",
  "Не удалось удалить аккаунт": "Could not delete the account",
  "Не удалось загрузить список": "Could not load the list",
  "владелец": "owner",
  "редактор": "editor",
  "разбор": "study",
};
