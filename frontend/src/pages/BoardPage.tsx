import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  type Edge,
  type Node,
  type ReactFlowInstance,
} from "@xyflow/react";
import {
  ArrowLeft,
  BookOpen,
  CircleHelp,
  Download,
  Ellipsis,
  Settings,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type NodeUpdate } from "../api";
import { BandsNode } from "../components/BandsNode";
import { BlockGroupNode } from "../components/BlockGroupNode";
import { LangSwitch } from "../components/LangSwitch";
import { SettingsMenu } from "../components/SettingsMenu";
import { nWord, useT } from "../i18n";
import { DetailDrawer } from "../components/DetailDrawer";
import { GuidesNode } from "../components/GuidesNode";
import { QuestionNode } from "../components/QuestionNode";
import { ShortcutsHelp } from "../components/ShortcutsHelp";
import { SubHeadNode } from "../components/SubHeadNode";
import { downloadBank } from "../report";
import {
  CARD_H,
  CARD_W,
  LABEL_W,
  subOf,
  swimlaneLayout,
  type Placement,
} from "../layout";
import {
  blockColor,
  blockLabel,
  blockOrder,
  hexA,
  levelColor,
  levelLabel,
  levelOrder,
  lighten,
  type ImportErr,
  type PoolConfig,
  type Progress,
  type QNode,
} from "../types";
import { href } from "../router";

const nodeTypes = {
  question: QuestionNode,
  blockGroup: BlockGroupNode,
  subhead: SubHeadNode,
  bands: BandsNode,
  guides: GuidesNode,
};
const NO_EDGES: Edge[] = [];

// M:SS из миллисекунд (для таймеров карточки и всего разбора).
function mmss(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// Совпадение ноды с поисковым запросом (подстрока в title/question/topic/tags).
function matchesQuery(n: QNode, q: string): boolean {
  if (!q) return true;
  return `${n.title ?? ""} ${n.question} ${n.topic} ${n.tags.join(" ")}`.toLowerCase().includes(q);
}

// Dropdown'ы toolbar'а (экспорт, •••) закрываются кликом мимо и Esc. Esc глушим в capture-фазе:
// иначе глобальный хоткей доски снимет текущий вопрос. mousedown — тоже capture: канва React Flow
// гасит всплытие. «Мимо» — всё вне корня dropdown'а (`within`: кнопка + меню).
function useDismiss(open: boolean, close: () => void, within: string) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      e.stopImmediatePropagation();
      close();
    };
    const onDown = (e: MouseEvent) => {
      const el = e.target as Element | null;
      if (el && el.closest(within)) return;
      close();
    };
    window.addEventListener("keydown", onKey, { capture: true });
    document.addEventListener("mousedown", onDown, { capture: true });
    return () => {
      window.removeEventListener("keydown", onKey, { capture: true });
      document.removeEventListener("mousedown", onDown, { capture: true });
    };
  }, [open, close, within]);
}

// Иконки toolbar'а — только outline Lucide с единым stroke-width (как на главной).
const ICON = { strokeWidth: 1.75 } as const;

// Настройки отображения холста (фон + направляющие), сохраняются в localStorage.
// База — без сетки; точки — единственный альтернативный вариант (переключается иконкой).
type BgVariant = "off" | "dots";

function buildNodes(
  graph: QNode[],
  pool: PoolConfig,
  p: Placement,
  bandCounts: Record<string, { done: number; count: number }>,
  statuses: Record<string, Progress>,
  currentId: string | null,
  selectedId: string | null,
  activeBlocks: Record<string, boolean>,
  activeDiffs: Record<string, boolean>,
  activeTags: Record<string, boolean>,
  activeKinds: Record<string, boolean>,
  query: string,
  unresolvedOnly: boolean,
  hiddenIds: Set<string>,
  showHidden: boolean,
  guidesH: boolean,
  guidesV: boolean,
  dark: boolean,
): Node[] {
  const nodes: Node[] = [];
  const anyTag = Object.values(activeTags).some(Boolean);

  nodes.push({
    id: "bg-bands",
    type: "bands",
    position: { x: -LABEL_W, y: 0 },
    data: {
      bands: p.bands.map((b) => ({ ...b, ...(bandCounts[b.difficulty] ?? { done: 0, count: 0 }) })),
      width: p.width,
      labelW: LABEL_W,
      height: p.height,
      dark,
    },
    draggable: false,
    selectable: false,
    zIndex: -5,
  });

  if (guidesH || guidesV) {
    nodes.push({
      id: "bg-guides",
      type: "guides",
      position: { x: 0, y: 0 },
      data: { columns: p.columns, bands: p.bands, width: p.width, height: p.height, guidesH, guidesV },
      draggable: false,
      selectable: false,
      zIndex: -4,
    });
  }

  for (const bg of p.blockGroups) {
    const blockNodes = graph.filter((n) => n.block === bg.block);
    // Готово = разобранные («знаю») по чек-листу.
    const done = blockNodes.filter((n) => statuses[n.id] === "known").length;
    nodes.push({
      id: `bg-${bg.block}`,
      type: "blockGroup",
      position: { x: bg.x, y: 0 },
      data: {
        block: bg.block,
        label: blockLabel(pool, bg.block),
        color: blockColor(pool, bg.block),
        width: bg.width,
        height: bg.height,
        count: blockNodes.length,
        done,
        split: bg.split,
        dark,
      },
      draggable: false,
      selectable: false,
      zIndex: -6,
    });
  }

  for (const col of p.columns) {
    if (!col.label) continue;
    const colNodes = graph.filter((n) => n.block === col.block && subOf(n) === col.subblock);
    const done = colNodes.filter((n) => statuses[n.id] === "known").length;
    nodes.push({
      id: `sh-${col.block}-${col.subblock}`,
      type: "subhead",
      position: { x: col.x, y: 0 },
      data: {
        block: col.block,
        label: col.label,
        color: blockColor(pool, col.block),
        width: col.width,
        count: colNodes.length,
        done,
        dark,
      },
      draggable: false,
      selectable: false,
      zIndex: -3,
    });
  }

  for (const n of graph) {
    const pos = p.positions[n.id];
    if (!pos) continue;
    const tagOk = !anyTag || n.tags.some((t) => activeTags[t]);
    // hide-local: скрытый вопрос гасится (если не показываем скрытые); при показе — помечается.
    const hidden = hiddenIds.has(n.id);
    const dimmed =
      activeBlocks[n.block] === false ||
      activeDiffs[n.difficulty] === false ||
      !activeKinds[n.kind] ||
      !tagOk ||
      !matchesQuery(n, query) ||
      (unresolvedOnly && statuses[n.id] === "known") ||
      (hidden && !showHidden);
    nodes.push({
      id: n.id,
      type: "question",
      position: pos,
      // Явные размеры (= размер карточки) нужны минимапе React Flow, иначе ноды не рисуются.
      width: CARD_W,
      height: CARD_H,
      data: {
        node: n,
        pool,
        color: blockColor(pool, n.block),
        dark,
        status: statuses[n.id],
        current: n.id === currentId,
        dimmed,
        hidden: hidden && showHidden,
      },
      selected: n.id === selectedId,
      draggable: false,
      selectable: !dimmed,
      style: dimmed ? { pointerEvents: "none" } : undefined,
      zIndex: n.id === currentId ? 5 : n.id === selectedId ? 4 : 1,
    });
  }
  return nodes;
}

// Ключи доски теперь с суффиксом пула, чтобы DE и SA не пересекались. Старый ключ без
// суффикса принадлежит бывшему единственному банку — переносим его в data-engineer один раз.
function legacyKey(base: string, pool: string): string {
  const key = `${base}:${pool}`;
  try {
    if (pool === "data-engineer" && localStorage.getItem(key) == null) {
      const old = localStorage.getItem(base);
      if (old != null) {
        localStorage.setItem(key, old);
        localStorage.removeItem(base);
      }
    }
  } catch { /* приват-режим */ }
  return key;
}

// hide-local: набор локально скрытых id (в localStorage). Читаем безопасно.
function readHiddenIds(pool: string): Set<string> {
  try {
    const raw = JSON.parse(localStorage.getItem(legacyKey("hiddenIds", pool)) || "[]");
    return new Set(Array.isArray(raw) ? raw.filter((x) => typeof x === "string") : []);
  } catch {
    return new Set();
  }
}

// Чек-лист разбора: клавиша → статус (1=знаю, 2=повторить, 3=не знаю), вне сессии.
const STATUS_BY_KEY: Record<string, Progress> = { "1": "known", "2": "review", "3": "unknown" };

const KINDS = ["question", "task"] as const;
const KIND_LABEL: Record<string, string> = { question: "вопрос", task: "задача" };
const KIND_COLOR: Record<string, string> = { question: "#2563eb", task: "#9333ea" };
const ALL_KINDS: Record<string, boolean> = { question: true, task: true };

export default function BoardPage({ pool }: { pool: PoolConfig }) {
  const t = useT();
  const [graph, setGraph] = useState<QNode[]>([]);
  const [errors, setErrors] = useState<ImportErr[]>([]);
  const [placement, setPlacement] = useState<Placement | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  // hide-local: скрытые с доски вопросы (клиентски) + тумблер показа.
  const [hiddenIds, setHiddenIds] = useState<Set<string>>(() => readHiddenIds(pool.id));
  const [showHidden, setShowHidden] = useState(false);
  // Чек-лист разбора (per-user): known|review|unknown по видимым нодам пула.
  const [statuses, setStatuses] = useState<Record<string, Progress>>({});
  const [unresolvedOnly, setUnresolvedOnly] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  // Таймер разбора: отсчёт с первой выбранной карточки, переживает перезагрузку (localStorage).
  const [studyStart, setStudyStart] = useState<number | null>(() => {
    const v = localStorage.getItem(legacyKey("timerStart", pool.id));
    return v ? Number(v) : null;
  });
  const [cardStart, setCardStart] = useState<number>(() => Date.now());
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  // Dropdown'ы toolbar'а: «Экспорт» и «•••».
  const [exportOpen, setExportOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [activeBlocks, setActiveBlocks] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(blockOrder(pool).map((b) => [b, true])),
  );
  // Уровни пула — задаются pool.levels; набор пересчитывается при смене пула (см. эффект ниже).
  const allDiffs = useMemo(() => Object.fromEntries(levelOrder(pool).map((d) => [d, true])), [pool]);
  const [activeDiffs, setActiveDiffs] = useState<Record<string, boolean>>(allDiffs);
  // BoardPage перемонтируется по key={pool.id} (см. Router.tsx), но фильтр уровней подстраховываем
  // явным сбросом — набор уровней у нового пула не совпадает со старым.
  useEffect(() => setActiveDiffs(allDiffs), [pool.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const [activeTags, setActiveTags] = useState<Record<string, boolean>>({});
  const [activeKinds, setActiveKinds] = useState<Record<string, boolean>>(ALL_KINDS);
  const [query, setQuery] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">(
    () =>
      (localStorage.getItem("theme") as "light" | "dark") ||
      (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"),
  );
  const [bgVariant, setBgVariant] = useState<BgVariant>(
    () => (localStorage.getItem("bgVariant") === "dots" ? "dots" : "off"),
  );
  const [guidesH, setGuidesH] = useState<boolean>(() => localStorage.getItem("guidesH") === "1");
  const [guidesV, setGuidesV] = useState<boolean>(() => localStorage.getItem("guidesV") === "1");
  // Таймер в HUD по умолчанию скрыт: тикающие цифры в поле зрения давят.
  const [showTimer, setShowTimer] = useState<boolean>(() => localStorage.getItem("showTimer") === "1");
  // Оформление доски (итог design-funnel): дефолт — 37 «Брутализм в цвете»,
  // альтернативы переключаются в ⚙. Применяется атрибутом data-design (design-themes.css).
  const [design, setDesign] = useState<string>(() => {
    const v = localStorage.getItem("design");
    return v && ["37", "56", "57", "58"].includes(v) ? v : "37";
  });
  // Панель фильтров — popover у правого края канвы, открывается кнопкой toolbar'а; по умолчанию
  // закрыта (поверх канвы она съедает правую треть доски), выбор запоминается.
  const [filtersOpen, setFiltersOpen] = useState<boolean>(
    () => localStorage.getItem("filtersOpen") === "1",
  );
  const closeExport = useCallback(() => setExportOpen(false), []);
  const closeMore = useCallback(() => setMoreOpen(false), []);
  useDismiss(exportOpen, closeExport, ".tbdrop--export");
  useDismiss(moreOpen, closeMore, ".tbdrop--more");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);
  useEffect(() => localStorage.setItem("bgVariant", bgVariant), [bgVariant]);
  useEffect(() => localStorage.setItem("guidesH", guidesH ? "1" : "0"), [guidesH]);
  useEffect(() => localStorage.setItem("guidesV", guidesV ? "1" : "0"), [guidesV]);
  useEffect(() => localStorage.setItem("showTimer", showTimer ? "1" : "0"), [showTimer]);
  useEffect(() => {
    document.documentElement.dataset.design = design;
    localStorage.setItem("design", design);
  }, [design]);
  useEffect(() => localStorage.setItem("filtersOpen", filtersOpen ? "1" : "0"), [filtersOpen]);
  // hide-local: персист набора скрытых id.
  useEffect(
    () => localStorage.setItem(`hiddenIds:${pool.id}`, JSON.stringify([...hiddenIds])),
    [hiddenIds, pool.id],
  );

  // hide-local: скрыть/вернуть вопрос на доску (клиентски, не трогает банк/БД).
  const toggleHide = useCallback((id: string) => {
    setHiddenIds((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // Таймеры: сброс «времени на карточку» при смене текущей; старт общего таймера при первом выборе.
  useEffect(() => {
    if (!currentId) return;
    setCardStart(Date.now());
    setStudyStart((s) => {
      if (s != null) return s;
      const t = Date.now();
      localStorage.setItem(`timerStart:${pool.id}`, String(t));
      return t;
    });
  }, [currentId, pool.id]);
  useEffect(() => {
    if (!currentId && studyStart == null) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [currentId, studyStart]);

  const instance = useRef<ReactFlowInstance<Node, Edge> | null>(null);
  const canvasRef = useRef<HTMLDivElement | null>(null);

  // Стартовый viewport: зум 0.5 (карточки читаются), доска — по центру канвы. Если доска шире
  // или выше канвы, прижимаем её к левому/верхнему краю с отступом, чтобы первая карточка была
  // в кадре. Доска в board-координатах занимает x ∈ [-LABEL_W, width], y ∈ [0, height].
  const centerBoard = useCallback(() => {
    const inst = instance.current;
    const el = canvasRef.current;
    if (!inst || !el || !placement) return;
    const zoom = 0.5;
    const bw = (LABEL_W + placement.width) * zoom;
    const bh = placement.height * zoom;
    // Открытая панель фильтров лежит поверх канвы справа — центрируем в свободной части.
    const panel = filtersOpen ? el.querySelector<HTMLElement>(".filterpanel") : null;
    const cw = el.clientWidth - (panel ? panel.offsetWidth + 24 : 0);
    const ch = el.clientHeight;
    const x = (bw < cw - 40 ? (cw - bw) / 2 : 20) + LABEL_W * zoom;
    const y = bh < ch - 40 ? (ch - bh) / 2 : 20;
    inst.setViewport({ x, y, zoom });
  }, [placement, filtersOpen]);
  useEffect(() => {
    centerBoard();
  }, [centerBoard]);
  useEffect(() => {
    window.addEventListener("resize", centerBoard);
    return () => window.removeEventListener("resize", centerBoard);
  }, [centerBoard]);
  const nodeMap = useMemo(() => Object.fromEntries(graph.map((n) => [n.id, n])), [graph]);
  const allTags = useMemo(
    () => Array.from(new Set(graph.flatMap((n) => n.tags))).sort(),
    [graph],
  );
  // Видимый срез (активные фильтры) — для навигации по карточкам.
  const visibleIds = useMemo(() => {
    const anyTag = Object.values(activeTags).some(Boolean);
    const s = new Set<string>();
    for (const n of graph) {
      const tagOk = !anyTag || n.tags.some((t) => activeTags[t]);
      if (activeBlocks[n.block] !== false && activeDiffs[n.difficulty] !== false && activeKinds[n.kind] && tagOk) {
        s.add(n.id);
      }
    }
    return s;
  }, [graph, activeBlocks, activeDiffs, activeKinds, activeTags]);

  // Порядок обхода — порядок сетки (колонка за колонкой).
  const walkOrder = useMemo(() => (placement ? placement.order.flat() : []), [placement]);

  // Ruling C2: счётчики по рядам (уровням сложности) для BandsNode — по видимому срезу
  // (см. visibleIds); done = «знаю» по чек-листу.
  const bandCounts = useMemo(() => {
    const out: Record<string, { done: number; count: number }> = {};
    for (const n of graph) {
      if (!visibleIds.has(n.id)) continue;
      const b = (out[n.difficulty] ??= { done: 0, count: 0 });
      b.count++;
      if (statuses[n.id] === "known") b.done++;
    }
    return out;
  }, [graph, visibleIds, statuses]);

  const loadGraph = useCallback(
    () =>
      api
        .graph(pool.id)
        .then((g) => {
          setGraph(g.nodes);
          setErrors(g.errors);
          setPlacement(swimlaneLayout(g.nodes, pool));
        })
        .catch((err) => setErrors([{ file: "API", error: String(err) }])),
    [pool],
  );

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  useEffect(() => {
    api.progress(pool.id).then(setStatuses).catch(() => setStatuses({}));
  }, [pool.id]);

  // question-management: удалить вопрос из банка (DELETE → перечитать граф → снять выбор/оценку).
  const deleteNode = useCallback(
    async (id: string) => {
      try {
        await api.deleteNode(id);
      } catch {
        alert(t("Не удалось удалить вопрос"));
        return;
      }
      await loadGraph();
      setSelectedId((s) => (s === id ? null : s));
      setCurrentId((c) => (c === id ? null : c));
    },
    [loadGraph],
  );

  // question-management: правка структурных полей вопроса (PUT → перечитать граф).
  const updateNode = useCallback(
    async (id: string, fields: NodeUpdate) => {
      try {
        await api.updateNode(id, fields);
      } catch {
        alert(t("Не удалось сохранить изменения"));
        return;
      }
      await loadGraph();
    },
    [loadGraph],
  );

  const rfNodes = useMemo(
    () =>
      placement
        ? buildNodes(graph, pool, placement, bandCounts, statuses, currentId, selectedId, activeBlocks, activeDiffs, activeTags, activeKinds, query.toLowerCase().trim(), unresolvedOnly, hiddenIds, showHidden, guidesH, guidesV, theme === "dark")
        : [],
    [graph, pool, placement, bandCounts, statuses, currentId, selectedId, activeBlocks, activeDiffs, activeTags, activeKinds, query, unresolvedOnly, hiddenIds, showHidden, guidesH, guidesV, theme],
  );

  const centerOn = useCallback(
    (id: string) => {
      const pos = placement?.positions[id];
      if (pos && instance.current) {
        instance.current.setCenter(pos.x + CARD_W / 2, pos.y + CARD_H / 2, { zoom: 1, duration: 400 });
      }
    },
    [placement],
  );

  // Чек-лист разбора: статус карточки. Optimistic update + откат при ошибке;
  // повтор той же клавиши/кнопки с тем же статусом снимает его (DELETE вместо PUT).
  const setStatus = useCallback(
    (nodeId: string, status: Progress) => {
      const prevStatus = statuses[nodeId];
      const clearing = prevStatus === status;
      setStatuses((s) => {
        const next = { ...s };
        if (clearing) delete next[nodeId];
        else next[nodeId] = status;
        return next;
      });
      const request = clearing ? api.clearProgress(nodeId) : api.setProgress(nodeId, status);
      request.catch(() => {
        setStatuses((s) => {
          const next = { ...s };
          if (prevStatus == null) delete next[nodeId];
          else next[nodeId] = prevStatus;
          return next;
        });
      });
    },
    [statuses],
  );

  const onNodeClick = useCallback((_: unknown, node: Node) => {
    if (node.type !== "question") return;
    setSelectedId(node.id);
    setCurrentId(node.id);
  }, []);

  const moveCurrent = useCallback(
    (id: string) => {
      setCurrentId(id);
      centerOn(id);
    },
    [centerOn],
  );

  // «n»: следующая НЕРАЗОБРАННАЯ карточка по порядку обхода, с переносом по кругу.
  // Если неразобранных не осталось — просто следующая видимая.
  const nextUnresolved = useCallback(() => {
    if (!placement) return;
    // только видимый срез (активные фильтры)
    const flat = walkOrder.filter((id) => visibleIds.has(id));
    if (!flat.length) return;
    const start = currentId ? flat.indexOf(currentId) : -1;
    for (let k = 1; k <= flat.length; k++) {
      const id = flat[(start + k + flat.length) % flat.length];
      if (id && id !== currentId && statuses[id] !== "known") {
        moveCurrent(id);
        return;
      }
    }
    moveCurrent(flat[(start + 1 + flat.length) % flat.length]);
  }, [placement, currentId, statuses, moveCurrent, visibleIds, walkOrder]);

  // Хоткеи чек-листа (1-3): следующая ВИДИМАЯ карточка в порядке матрицы —
  // следующая в колонке, затем первая следующей колонки; те же фильтры и «только
  // неразобранное», что у nextUnresolved. Пусто после фильтра — остаёмся на месте.
  // Возвращает id новой текущей карточки (для drawer, п.2) или null.
  const nextInMatrix = useCallback((): string | null => {
    if (!placement) return null;
    const flat = walkOrder.filter((id) => visibleIds.has(id) && (!unresolvedOnly || statuses[id] !== "known"));
    if (!flat.length) return null;
    const idx = currentId ? flat.indexOf(currentId) : -1;
    const next = flat[(idx + 1 + flat.length) % flat.length];
    if (next) moveCurrent(next);
    return next ?? null;
  }, [placement, currentId, moveCurrent, walkOrder, visibleIds, unresolvedOnly, statuses]);

  // Клавиатура: 1-3 — статус чек-листа, Enter — открыть, стрелки — навигация,
  // n — следующая неразобранная, Esc — снять текущую.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
      // «?» открывает шпаргалку. Пока она открыта, ShortcutsHelp перехватывает клавиши в capture-фазе
      // (stopImmediatePropagation), поэтому сюда они не доходят и захват клавиатуры обеспечен там.
      if (e.key === "?") {
        setHelpOpen(true);
        return;
      }
      if (!placement) return;
      if (e.key in STATUS_BY_KEY) {
        if (!currentId) return;
        setStatus(currentId, STATUS_BY_KEY[e.key]);
        // Drawer открыт — курсор должен идти вместе с ним (иначе drawer «отстаёт»).
        const nextId = nextInMatrix();
        if (nextId != null && selectedId != null) setSelectedId(nextId);
        return;
      }
      if (e.key === "Enter") {
        if (currentId) setSelectedId(currentId);
        return;
      }
      if (e.key === "n") {
        nextUnresolved();
        return;
      }
      if (e.key === "Escape" && !selectedId) {
        setCurrentId(null);
        return;
      }
      if (!e.key.startsWith("Arrow")) return;
      e.preventDefault();
      if (!currentId) {
        const id = placement.order[0]?.[0];
        if (id) moveCurrent(id);
        return;
      }
      const col = placement.colOf[currentId] ?? 0;
      const row = placement.rowOf[currentId] ?? 0;
      let target: string | undefined;
      if (e.key === "ArrowDown") target = placement.order[col]?.[Math.min(row + 1, placement.order[col].length - 1)];
      else if (e.key === "ArrowUp") target = placement.order[col]?.[Math.max(row - 1, 0)];
      else if (e.key === "ArrowRight") {
        for (let c = col + 1; c < placement.order.length; c++) {
          const arr = placement.order[c];
          if (arr?.length) {
            target = arr[Math.min(row, arr.length - 1)];
            break;
          }
        }
      } else if (e.key === "ArrowLeft") {
        for (let c = col - 1; c >= 0; c--) {
          const arr = placement.order[c];
          if (arr?.length) {
            target = arr[Math.min(row, arr.length - 1)];
            break;
          }
        }
      }
      if (target) moveCurrent(target);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [placement, currentId, selectedId, moveCurrent, nextUnresolved, setStatus, nextInMatrix]);

  const toggleBlock = (b: string) => setActiveBlocks((s) => ({ ...s, [b]: !s[b] }));
  const toggleDiff = (d: string) => setActiveDiffs((s) => ({ ...s, [d]: !s[d] }));
  const toggleTag = (t: string) => setActiveTags((s) => ({ ...s, [t]: !s[t] }));
  const clearTags = () => setActiveTags({});
  const toggleKind = (k: string) => setActiveKinds((s) => ({ ...s, [k]: !s[k] }));

  // Прогресс по блокам для чипов фильтра: разобранные («знаю») из чек-листа.
  const blockProgress = useMemo(() => {
    const out: Record<string, { done: number; total: number }> = {};
    for (const b of blockOrder(pool)) out[b] = { done: 0, total: 0 };
    for (const n of graph) {
      out[n.block] ??= { done: 0, total: 0 };
      out[n.block].total++;
      if (statuses[n.id] === "known") out[n.block].done++;
    }
    return out;
  }, [graph, statuses, pool]);

  // Число разобранных («знаю») карточек — для HUD/toolbar.
  const known = useMemo(
    () => Object.values(statuses).filter((s) => s === "known").length,
    [statuses],
  );

  const anyTagActive = Object.values(activeTags).some(Boolean);
  // Свёрнутая панель не должна прятать факт, что доска отфильтрована, — отсюда точка-индикатор.
  const anyFilterOn =
    anyTagActive ||
    query.trim() !== "" ||
    unresolvedOnly ||
    blockOrder(pool).some((b) => !activeBlocks[b]) ||
    levelOrder(pool).some((d) => !activeDiffs[d]) ||
    KINDS.some((k) => !activeKinds[k]);
  const currentNode = currentId ? nodeMap[currentId] : null;
  const selectedNode = selectedId ? nodeMap[selectedId] : null;

  const nQuestions = `${graph.length} ${nWord(graph.length, ["вопрос", "вопроса", "вопросов"], ["question", "questions"])}`;

  return (
    <div className="app">
      {/* Toolbar (ТЗ 10–14): один ряд — слева «где мы» (назад, направление, число вопросов),
          справа действия (фильтры, экспорт, язык, •••). */}
      <header className="topbar">
        <div className="topbar__row topbar__row--main">
          <div className="topbar__left">
            <a className="topbar__back" href={href.home} title={t("Главное меню")}>
              <ArrowLeft size={16} {...ICON} aria-hidden="true" />
              {t("Направления")}
            </a>
            <h1 className="appname">{pool.label}</h1>
            <span className="topbar__count">{nQuestions}</span>
          </div>
          <div className="topbar__right">
            <button
              className="tbbtn filtersbtn"
              onClick={() => setFiltersOpen((v) => !v)}
              aria-pressed={filtersOpen}
              title={t("Фильтры вопросов")}
            >
              <SlidersHorizontal size={16} {...ICON} aria-hidden="true" />
              {t("Фильтры")}
              {anyFilterOn && <span className="filtersbtn__dot" title={t("Фильтры активны")} />}
            </button>
            <div className="tbdrop tbdrop--export">
              <button
                className="tbbtn exportbtn"
                onClick={() => setExportOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={exportOpen}
              >
                <Download size={16} {...ICON} aria-hidden="true" />
                {t("Экспорт")}
              </button>
              {exportOpen && (
                <div className="tbmenu exportmenu" role="menu">
                  <button
                    className="tbmenu__item bankbtn"
                    role="menuitem"
                    onClick={() => { setExportOpen(false); downloadBank(graph, pool); }}
                  >
                    {t("Банк вопросов (HTML)")}
                  </button>
                </div>
              )}
            </div>
            <LangSwitch />
            <div className="tbdrop tbdrop--more">
              <button
                className="tbbtn tbbtn--icon morebtn"
                onClick={() => setMoreOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={moreOpen}
                aria-label={t("Ещё")}
                title={t("Ещё")}
              >
                <Ellipsis size={18} {...ICON} />
              </button>
              {moreOpen && (
                <div className="tbmenu moremenu" role="menu">
                  <button
                    className="tbmenu__item setbtn"
                    role="menuitem"
                    onClick={() => { setMoreOpen(false); setSettingsOpen(true); }}
                  >
                    <Settings size={16} {...ICON} aria-hidden="true" />
                    {t("Настройки")}
                  </button>
                  <button
                    className="tbmenu__item helpbtn"
                    role="menuitem"
                    onClick={() => { setMoreOpen(false); setHelpOpen(true); }}
                  >
                    <CircleHelp size={16} {...ICON} aria-hidden="true" />
                    {t("Шпаргалка клавиш")}
                  </button>
                  <a className="tbmenu__item bankLink" role="menuitem" href={href.bank(pool.id)}>
                    <BookOpen size={16} {...ICON} aria-hidden="true" />
                    {t("Открыть вопросы")}
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>

      </header>

      {errors.length > 0 && (
        <div className="errbar">
          {t("⚠ Ошибки импорта ({n}):", { n: errors.length })}{" "}
          {errors.map((e, i) => (
            <span key={i} className="erritem">
              {e.file}: {e.error}
            </span>
          ))}
        </div>
      )}

      <div className="main">
        <div className="canvas" ref={canvasRef}>
          {rfNodes.length === 0 ? (
            <div className="loading">{t("Загрузка графа…")}</div>
          ) : (
            <ReactFlow
              nodes={rfNodes}
              edges={NO_EDGES}
              nodeTypes={nodeTypes}
              colorMode={theme}
              onNodeClick={onNodeClick}
              onInit={(inst) => {
                instance.current = inst;
                centerBoard();
              }}
              nodesDraggable={false}
              nodesConnectable={false}
              // Первый кадр до centerBoard: зум 0.5 (карточки ~140px, читаются при открытии).
              // Не fitView — тот ужимает все 61 карту до ~62px.
              defaultViewport={{ x: 20, y: 20, zoom: 0.5 }}
              minZoom={0.1}
              proOptions={{ hideAttribution: true }}
            >
              {bgVariant === "dots" && <Background variant={BackgroundVariant.Dots} gap={18} size={1.4} />}
              <Controls showInteractive={false} />
              <MiniMap
                nodeColor={(n) =>
                  n.type === "question"
                    ? ((n.data as { color?: string })?.color ?? "#999")
                    : "rgba(100,116,139,0.18)"
                }
                pannable
                zoomable
              />

              {filtersOpen && (
                <Panel position="top-right">
                  <div className="filterpanel" role="region" aria-label={t("Фильтры вопросов")}>
                    <div className="fp__head">
                      <h2 className="fp__heading">{t("Фильтры")}</h2>
                      <button
                        className="fp__close"
                        onClick={() => setFiltersOpen(false)}
                        aria-label={t("Закрыть фильтры")}
                        title={t("Закрыть фильтры")}
                      >
                        <X size={16} {...ICON} aria-hidden="true" />
                      </button>
                    </div>
                    <input
                      className="fp__search"
                      placeholder={t("Поиск по вопросам…")}
                      aria-label={t("Поиск по вопросам")}
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                    <div className="fp__group">
                      <h2 className="fp__title">{t("Блоки")}</h2>
                      {blockOrder(pool).map((b) => (
                        <button
                          key={b}
                          className={`fp__chip ${activeBlocks[b] ? "" : "fp__chip--off"}`}
                          style={{
                            borderColor: blockColor(pool, b),
                            color: activeBlocks[b] ? "#fff" : blockColor(pool, b),
                            background: activeBlocks[b] ? blockColor(pool, b) : "transparent",
                          }}
                          onClick={() => toggleBlock(b)}
                        >
                          {blockLabel(pool, b)} {blockProgress[b].done}/{blockProgress[b].total}
                        </button>
                      ))}
                    </div>
                    <div className="fp__group">
                      <h2 className="fp__title">{t("Сложность")}</h2>
                      {levelOrder(pool).map((d) => (
                        <button
                          key={d}
                          className={`fp__chip ${activeDiffs[d] ? "" : "fp__chip--off"}`}
                          style={{
                            borderColor: levelColor(pool, d),
                            color: activeDiffs[d] ? "#fff" : levelColor(pool, d),
                            background: activeDiffs[d] ? levelColor(pool, d) : "transparent",
                          }}
                          onClick={() => toggleDiff(d)}
                        >
                          {levelLabel(pool, d)}
                        </button>
                      ))}
                    </div>
                    <div className="fp__group">
                      <h2 className="fp__title">{t("Тип")}</h2>
                      {KINDS.map((k) => (
                        <button
                          key={k}
                          className={`fp__chip ${activeKinds[k] ? "" : "fp__chip--off"}`}
                          style={{
                            borderColor: KIND_COLOR[k],
                            color: activeKinds[k] ? "#fff" : KIND_COLOR[k],
                            background: activeKinds[k] ? KIND_COLOR[k] : "transparent",
                          }}
                          onClick={() => toggleKind(k)}
                        >
                          {t(KIND_LABEL[k])}
                        </button>
                      ))}
                    </div>
                    {/* Прогресс-фильтр: «только неразобранное» — гасит карточки со статусом «знаю». */}
                    <div className="fp__group">
                      <h2 className="fp__title">{t("Прогресс")}</h2>
                      <button
                        className={`fp__chip ${unresolvedOnly ? "" : "fp__chip--off"}`}
                        style={{
                          borderColor: "#16a34a",
                          color: unresolvedOnly ? "#fff" : "#16a34a",
                          background: unresolvedOnly ? "#16a34a" : "transparent",
                        }}
                        onClick={() => setUnresolvedOnly((v) => !v)}
                      >
                        {t("Только неразобранное")}
                      </button>
                    </div>
                    <div className="fp__group fp__group--tags">
                      <div className="fp__title">
                        {t("Теги")}
                        {anyTagActive && (
                          <button className="fp__clear" onClick={clearTags}>
                            {t("сбросить")}
                          </button>
                        )}
                      </div>
                      {allTags.map((tag) => (
                        <button
                          key={tag}
                          className={`fp__tag ${activeTags[tag] ? "fp__tag--on" : ""}`}
                          onClick={() => toggleTag(tag)}
                        >
                          {tag}
                        </button>
                      ))}
                    </div>
                  </div>
                </Panel>
              )}

              {currentNode && (
                <Panel position="bottom-center">
                  <div className="hud">
                    <span
                      className="hud__diff"
                      style={
                        theme === "dark"
                          ? {
                              background: hexA(levelColor(pool, currentNode.difficulty), 0.22),
                              color: lighten(levelColor(pool, currentNode.difficulty), 0.55),
                            }
                          : {
                              background: hexA(levelColor(pool, currentNode.difficulty), 0.15),
                              color: levelColor(pool, currentNode.difficulty),
                            }
                      }
                    >
                      {levelLabel(pool, currentNode.difficulty)}
                    </span>
                    <span className="hud__title" title={currentNode.question}>
                      {currentNode.title || currentNode.question}
                    </span>
                    {showTimer && (
                      <span className="hud__timer" title={t("Время на карточку · весь разбор")}>
                        ⏱ {mmss(now - cardStart)}
                        {studyStart != null && ` · ${mmss(now - studyStart)}`}
                      </span>
                    )}
                    <span className="hud__progress">
                      {`${t("Разобрано")} ${known}/${graph.length}`}
                      {" · "}
                      {currentNode.topic}
                    </span>
                    {/* HUD ставит статусы чек-листа: знаю / повторить / не знаю. */}
                    <span className="hud__score">
                      <button
                        className={`statusbtn statusbtn--known ${statuses[currentId!] === "known" ? "statusbtn--on" : ""}`}
                        onClick={() => setStatus(currentId!, "known")}
                      >
                        {t("Знаю (1)")}
                      </button>
                      <button
                        className={`statusbtn statusbtn--review ${statuses[currentId!] === "review" ? "statusbtn--on" : ""}`}
                        onClick={() => setStatus(currentId!, "review")}
                      >
                        {t("Повторить (2)")}
                      </button>
                      <button
                        className={`statusbtn statusbtn--unknown ${statuses[currentId!] === "unknown" ? "statusbtn--on" : ""}`}
                        onClick={() => setStatus(currentId!, "unknown")}
                      >
                        {t("Не знаю (3)")}
                      </button>
                    </span>
                    <button onClick={() => setSelectedId(currentId)}>{t("Открыть")}</button>
                    <button className="hud__cancel" onClick={() => setCurrentId(null)} title={t("Снять выбор (Esc)")}>
                      ✕
                    </button>
                  </div>
                </Panel>
              )}
            </ReactFlow>
          )}
        </div>

        <DetailDrawer
          node={selectedNode}
          pool={pool}
          status={selectedId ? statuses[selectedId] : undefined}
          onStatus={setStatus}
          fullscreen={fullscreen}
          hidden={selectedId ? hiddenIds.has(selectedId) : false}
          onToggleHide={toggleHide}
          onDelete={deleteNode}
          onUpdate={updateNode}
          onToggleFullscreen={() => setFullscreen((f) => !f)}
          onClose={() => {
            setSelectedId(null);
            setFullscreen(false);
          }}
        />
      </div>
      {/* Панель ⚙ (открывается из •••): fixed-drawer слева; обёртка .settings нужна её проверке «клик мимо». */}
      {settingsOpen && (
        <div className="settings">
          <SettingsMenu
            onClose={() => setSettingsOpen(false)}
            settings={{
              design,
              onSetDesign: setDesign,
              theme,
              onToggleTheme: () => setTheme((t) => (t === "dark" ? "light" : "dark")),
              bgDots: bgVariant === "dots",
              onToggleBgDots: () => setBgVariant((v) => (v === "dots" ? "off" : "dots")),
              guidesV,
              onToggleGuidesV: () => setGuidesV((v) => !v),
              guidesH,
              onToggleGuidesH: () => setGuidesH((v) => !v),
              showHidden,
              onToggleHidden: () => setShowHidden((v) => !v),
              hiddenCount: hiddenIds.size,
              showTimer,
              onToggleTimer: () => setShowTimer((v) => !v),
              onShowHelp: () => setHelpOpen(true),
              bankHref: href.bank(pool.id),
            }}
          />
        </div>
      )}
      {helpOpen && <ShortcutsHelp onClose={() => setHelpOpen(false)} />}
    </div>
  );
}
