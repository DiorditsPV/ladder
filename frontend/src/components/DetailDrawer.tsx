import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent } from "react";
import Markdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import { blockColor, blockLabel, levelLabel, levelOrder, type PoolConfig, type Progress, type QNode } from "../types";
import type { NodeUpdate } from "../api";
import { useT } from "../i18n";

// Два режима показа открытой карточки (решение владельца 2026-09-11):
// - center (по умолчанию) — плавающая карточка по центру доски: ответ скрыт до «Показать ответ» / пробела,
//   внизу статусы чек-листа и ‹ › по матрице; доска вокруг видна и кликается (затемнения нет);
// - side — панель справа, как раньше: ответ виден сразу, ширина тянется ручкой на левом краю.
// Корень обоих — `.drawer` (на него ходит smoke) + модификатор `.drawer--center` / `.drawer--side`.
export type CardMode = "center" | "side";

const MODE_KEY = "ladder.cardMode";
const WIDTH_KEY = "ladder.drawerWidth";
const DRAWER_W_DEFAULT = 460;
const DRAWER_W_MIN = 360;
const DRAWER_W_MAX = 1100;

export function readCardMode(): CardMode {
  try {
    return localStorage.getItem(MODE_KEY) === "side" ? "side" : "center";
  } catch {
    return "center";
  }
}

export function saveCardMode(mode: CardMode): void {
  try {
    localStorage.setItem(MODE_KEY, mode);
  } catch {
    /* приватный режим — режим живёт до перезагрузки */
  }
}

// Ширина панели: от 360px до min(75vw, 1100px). Верхняя граница по окну — ещё и в CSS (max-width),
// чтобы сужение окна не оставляло панель шире допустимого до следующей отрисовки.
function clampWidth(w: number): number {
  const max = Math.max(DRAWER_W_MIN, Math.min(window.innerWidth * 0.75, DRAWER_W_MAX));
  return Math.round(Math.min(Math.max(w, DRAWER_W_MIN), max));
}

function readDrawerWidth(): number {
  try {
    const v = Number(localStorage.getItem(WIDTH_KEY));
    return Number.isFinite(v) && v > 0 ? Math.min(Math.max(v, DRAWER_W_MIN), DRAWER_W_MAX) : DRAWER_W_DEFAULT;
  } catch {
    return DRAWER_W_DEFAULT;
  }
}

function saveDrawerWidth(w: number | null): void {
  try {
    if (w == null) localStorage.removeItem(WIDTH_KEY);
    else localStorage.setItem(WIDTH_KEY, String(w));
  } catch {
    /* приватный режим */
  }
}

// Поле ввода — пробел в нём печатает, а не раскрывает ответ.
function isEditable(el: EventTarget | null): boolean {
  const n = el as HTMLElement | null;
  if (!n || !n.tagName) return false;
  return n.tagName === "INPUT" || n.tagName === "TEXTAREA" || n.tagName === "SELECT" || n.isContentEditable;
}

// Клик мышью по кнопке оставляет на ней фокус, и следующий пробел нажал бы её снова (например, › вместо
// «Показать ответ»). Снимаем фокус только у кликов мышью (detail > 0): с клавиатуры фокус остаётся на месте.
function blurAfterMouse(e: ReactMouseEvent<HTMLButtonElement>): void {
  if (e.detail > 0) e.currentTarget.blur();
}

interface Props {
  node: QNode | null;
  pool: PoolConfig;
  mode: CardMode;
  onSetMode: (mode: CardMode) => void;
  // Соседние карточки по матрице доски (те же фильтры и «только неразобранное», что у хоткеев).
  onPrev: () => void;
  onNext: () => void;
  // Чек-лист разбора: статус текущей карточки + сеттер.
  status?: Progress;
  onStatus: (nodeId: string, status: Progress) => void;
  fullscreen: boolean;
  hidden: boolean;
  onToggleHide: (nodeId: string) => void;
  // Правка и удаление карточки — только у ролей с правом на контент (не демо и не viewer).
  // «Скрыть» — локальная настройка вида в браузере, остаётся у всех.
  canEdit: boolean;
  onDelete: (nodeId: string) => void;
  onUpdate: (nodeId: string, fields: NodeUpdate) => void;
  onToggleFullscreen: () => void;
  onClose: () => void;
}

// Немодальная карточка вопроса: полный текст вопроса/ответа. Закрывается с клавиатуры (Esc).
export function DetailDrawer({
  node, pool, mode, onSetMode, onPrev, onNext, status, onStatus, fullscreen, hidden, onToggleHide,
  canEdit, onDelete, onUpdate, onToggleFullscreen, onClose,
}: Props) {
  const t = useT();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<{ title: string; difficulty: string; question: string; answer: string }>(
    { title: "", difficulty: pool.levels[0]?.id ?? "", question: "", answer: "" },
  );
  // Ответ раскрыт у карточки с этим id: переход к другой карточке снова прячет ответ — без кадра,
  // в котором новая карточка успела бы показать свой ответ (как было бы со сбросом в эффекте).
  const [revealedId, setRevealedId] = useState<string | null>(null);
  const [width, setWidth] = useState(readDrawerWidth);
  const [resizing, setResizing] = useState(false);
  const asideRef = useRef<HTMLElement | null>(null);

  const center = mode === "center";
  const revealed = !center || (node != null && revealedId === node.id);

  // Сброс режима правки при переключении на другой вопрос.
  useEffect(() => setEditing(false), [node?.id]);
  // Справа ответ виден сразу — такую карточку считаем раскрытой: переход «Справа → По центру» не прячет
  // ответ, который уже читали.
  useEffect(() => {
    if (!center && node) setRevealedId(node.id);
  }, [center, node]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (editing) setEditing(false);
        else onClose();
        return;
      }
      // Пробел раскрывает ответ карточки по центру — только пока он скрыт и фокус не в поле ввода;
      // в остальных случаях пробел ведёт себя как обычно (нажимает кнопку в фокусе и т.п.).
      if (e.key === " " && center && node && !editing && revealedId !== node.id && !isEditable(e.target)) {
        e.preventDefault();
        setRevealedId(node.id);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, editing, center, node, revealedId]);

  // Пока тянем ручку — курсор col-resize и без выделения текста по всей странице.
  useEffect(() => {
    if (!resizing) return;
    document.body.classList.add("is-resizing");
    return () => document.body.classList.remove("is-resizing");
  }, [resizing]);

  if (!node) return null;
  const color = blockColor(pool, node.block);
  const isTask = node.kind === "task";

  const startEdit = () => {
    setDraft({ title: node.title ?? "", difficulty: node.difficulty, question: node.question, answer: node.answer });
    setEditing(true);
  };
  const saveEdit = () => {
    onUpdate(node.id, {
      title: draft.title.trim() || undefined,
      difficulty: draft.difficulty,
      question: draft.question,
      answer: draft.answer,
    });
    setEditing(false);
  };
  const confirmDelete = () => {
    if (window.confirm(t("Удалить вопрос «{name}» из банка безвозвратно?", { name: node.title || node.id }))) {
      onDelete(node.id);
    }
  };

  // Ручка ширины (режим side): тянем левый край, правый край панели стоит на месте.
  // Сохраняем по отпусканию и только если ширину действительно тянули (клик без движения — не выбор).
  const onResizeStart = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 || !asideRef.current) return;
    e.preventDefault();
    const handle = e.currentTarget;
    const right = asideRef.current.getBoundingClientRect().right;
    let last: number | null = null;
    handle.setPointerCapture(e.pointerId);
    setResizing(true);
    const move = (ev: PointerEvent) => {
      last = clampWidth(right - ev.clientX);
      setWidth(last);
    };
    const end = () => {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", end);
      handle.removeEventListener("pointercancel", end);
      setResizing(false);
      if (last != null) saveDrawerWidth(last);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", end);
    handle.addEventListener("pointercancel", end);
  };
  const resetWidth = () => {
    setWidth(DRAWER_W_DEFAULT);
    saveDrawerWidth(null);
  };

  const statusButtons = (
    <div className="statusbar">
      <button
        className={`statusbtn statusbtn--known ${status === "known" ? "statusbtn--on" : ""}`}
        onClick={(e) => { blurAfterMouse(e); onStatus(node.id, "known"); }}
      >
        {t("Знаю (1)")}
      </button>
      <button
        className={`statusbtn statusbtn--review ${status === "review" ? "statusbtn--on" : ""}`}
        onClick={(e) => { blurAfterMouse(e); onStatus(node.id, "review"); }}
      >
        {t("Повторить (2)")}
      </button>
      <button
        className={`statusbtn statusbtn--unknown ${status === "unknown" ? "statusbtn--on" : ""}`}
        onClick={(e) => { blurAfterMouse(e); onStatus(node.id, "unknown"); }}
      >
        {t("Не знаю (3)")}
      </button>
    </div>
  );

  const hideButton = (
    <button
      className="drawer__hide"
      onClick={() => onToggleHide(node.id)}
      title={hidden ? t("Вернуть на доску") : t("Скрыть с доски (локально, обратимо)")}
    >
      {hidden ? t("Вернуть") : t("Скрыть")}
    </button>
  );
  const deleteButton = canEdit && (
    <button className="drawer__delete" onClick={confirmDelete} title={t("Удалить вопрос из банка (необратимо)")}>
      {t("Удалить")}
    </button>
  );
  const editButton = canEdit && !editing && (
    <button className="drawer__edit" onClick={startEdit} title={t("Редактировать вопрос (в банке)")}>
      {t("Редактировать")}
    </button>
  );
  const closeButton = (
    <button className="drawer__close" onClick={onClose} title={t("Закрыть (Esc)")} aria-label={t("Закрыть (Esc)")}>
      ✕
    </button>
  );

  const editForm = (
    <div className="drawer__editform">
      <label className="drawer__field">
        {t("Заголовок")}
        <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
      </label>
      <label className="drawer__field">
        {t("Сложность")}
        <select
          value={draft.difficulty}
          onChange={(e) => setDraft({ ...draft, difficulty: e.target.value })}
        >
          {levelOrder(pool).map((d) => (
            <option key={d} value={d}>{levelLabel(pool, d)}</option>
          ))}
        </select>
      </label>
      <label className="drawer__field">
        {isTask ? t("Задача") : t("Вопрос")}
        <textarea rows={4} value={draft.question} onChange={(e) => setDraft({ ...draft, question: e.target.value })} />
      </label>
      <label className="drawer__field">
        {isTask ? t("Эталон / решение") : t("Ответ")}
        <textarea rows={8} value={draft.answer} onChange={(e) => setDraft({ ...draft, answer: e.target.value })} />
      </label>
      <div className="drawer__editbtns">
        <button className="btn--primary" onClick={saveEdit} disabled={!draft.question.trim()}>
          {t("💾 Сохранить")}
        </button>
        <button onClick={() => setEditing(false)}>{t("Отмена")}</button>
      </div>
    </div>
  );

  const questionSection = (
    <section>
      <h2>{isTask ? t("Задача") : t("Вопрос")}</h2>
      <div className="md">
        <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
          {node.question}
        </Markdown>
      </div>
    </section>
  );

  // Всё, что прячется под «Показать ответ»: у задач — и стартовый код, и эталон, и критерии.
  const answerBlock = (
    <div className="drawer__answer">
      {node.starterCode && (
        <section>
          <h3>{t("Стартовый код")}</h3>
          <div className="md">
            <Markdown rehypePlugins={[rehypeHighlight]}>
              {"```python\n" + node.starterCode + "\n```"}
            </Markdown>
          </div>
        </section>
      )}

      <section>
        <h2>{isTask ? t("Эталон / решение") : t("Ответ")}</h2>
        <div className="md">
          <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
            {node.answer}
          </Markdown>
        </div>
      </section>

      {node.rubric.length > 0 && (
        <section>
          <h3>{t("Критерии самопроверки")}</h3>
          <ul className="rubric">
            {node.rubric.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );

  if (center) {
    return (
      <aside
        ref={asideRef}
        className="drawer drawer--center"
        role="dialog"
        aria-label={t("Детали вопроса")}
        aria-modal="false"
        tabIndex={-1}
        style={{ borderTopColor: color }}
      >
        <header className="drawer__bar">
          <span className="drawer__badge" style={{ background: color }}>
            {blockLabel(pool, node.block)} · {levelLabel(pool, node.difficulty)}
          </span>
          <div className="drawer__actions">
            <button
              className="drawer__mode"
              onClick={() => onSetMode("side")}
              title={t("Показывать карточку в панели справа")}
            >
              {t("Справа")}
            </button>
            {editButton}
            {deleteButton}
            {hideButton}
            {closeButton}
          </div>
          {node.title && <h1 className="drawer__title">{node.title}</h1>}
        </header>

        <div className="drawer__body">
          {editing ? editForm : (
            <>
              {questionSection}
              {revealed ? answerBlock : (
                <button
                  className="drawer__reveal"
                  onClick={() => setRevealedId(node.id)}
                  aria-keyshortcuts="Space"
                >
                  {t("Показать ответ")}
                  <kbd>Space</kbd>
                </button>
              )}
            </>
          )}
        </div>

        {!editing && (
          <footer className="drawer__foot">
            <button
              className="drawer__prev"
              onClick={(e) => { blurAfterMouse(e); onPrev(); }}
              aria-label={t("Предыдущая карточка")}
              title={t("Предыдущая карточка")}
            >
              <ChevronLeft size={18} strokeWidth={2} aria-hidden="true" />
            </button>
            {statusButtons}
            <button
              className="drawer__next"
              onClick={(e) => { blurAfterMouse(e); onNext(); }}
              aria-label={t("Следующая карточка")}
              title={t("Следующая карточка")}
            >
              <ChevronRight size={18} strokeWidth={2} aria-hidden="true" />
            </button>
          </footer>
        )}
      </aside>
    );
  }

  return (
    <aside
      ref={asideRef}
      className={`drawer drawer--side ${fullscreen ? "drawer--full" : ""} ${resizing ? "drawer--resizing" : ""}`}
      role="dialog"
      aria-label={t("Детали вопроса")}
      aria-modal="false"
      tabIndex={-1}
      style={{ "--drawer-w": `${clampWidth(width)}px` } as CSSProperties}
    >
      {!fullscreen && (
        <div
          className="drawer__resize"
          onPointerDown={onResizeStart}
          onDoubleClick={resetWidth}
          title={t("Потяните, чтобы изменить ширину; двойной клик — ширина по умолчанию")}
          aria-hidden="true"
        />
      )}
      <header className="drawer__bar" style={{ borderTopColor: color }}>
        <span className="drawer__badge" style={{ background: color }}>
          {blockLabel(pool, node.block)} · {node.topic}
        </span>
        <span className="drawer__diff">
          {isTask ? t("🛠 задача") : t("❓ вопрос")} · {levelLabel(pool, node.difficulty)}
        </span>
        <div className="drawer__actions">
          {hideButton}
          {deleteButton}
          {editButton}
          <button
            className="drawer__mode"
            onClick={() => onSetMode("center")}
            title={t("Показывать карточку по центру доски")}
          >
            {t("По центру")}
          </button>
          <button onClick={onToggleFullscreen} title={t("Развернуть/свернуть")}>
            {fullscreen ? t("Свернуть") : t("На весь экран")}
          </button>
          {closeButton}
        </div>
      </header>

      <div className="drawer__body">
        {editing ? editForm : (
          <>
            {node.title && <h1 className="drawer__title">{node.title}</h1>}

            {node.tags.length > 0 && (
              <div className="drawer__tags">
                {node.tags.map((tag) => (
                  <span key={tag} className="tagchip">
                    {tag}
                  </span>
                ))}
              </div>
            )}

            {questionSection}
            {answerBlock}

            <section className="drawer__scoring">
              <h3>{t("Разобрано")}</h3>
              {statusButtons}
            </section>
          </>
        )}
      </div>
    </aside>
  );
}
