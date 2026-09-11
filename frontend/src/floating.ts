import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
  type RefObject,
} from "react";

// Плавающие окна над доской (решение владельца 2026-09-11): окно карточки по центру и окно фильтров.
// Место по умолчанию задаёт CSS (по центру доски / у правого края), а пользователь двигает окно от
// него: сдвиг — transform: translate, хранится в localStorage как смещение от этого места, поэтому
// переживает смену размера окна браузера. Храним то, что выбрал человек, а рисуем поджатым внутрь
// области доски: сузил браузер — окно прижалось к краю, расширил обратно — вернулось на своё место.
// Тянут за шапку указателем (pointer capture: события не уходят канве React Flow), двойной клик по
// шапке — место по умолчанию. Кнопки в шапке ручкой не считаются.

export type Offset = { dx: number; dy: number };
const ZERO: Offset = { dx: 0, dy: 0 };
/** Зазор между окном и краем области доски. */
export const EDGE = 12;

function readOffset(key: string): Offset {
  try {
    const v = JSON.parse(localStorage.getItem(key) ?? "null");
    if (v && Number.isFinite(v.dx) && Number.isFinite(v.dy)) return { dx: v.dx, dy: v.dy };
  } catch {
    /* битое значение — место по умолчанию */
  }
  return ZERO;
}

function saveOffset(key: string, o: Offset): void {
  try {
    if (o.dx === 0 && o.dy === 0) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify({ dx: o.dx, dy: o.dy }));
  } catch {
    /* приватный режим — место живёт до перезагрузки */
  }
}

/** Кнопки и поля в шапке — не ручка перетаскивания. */
export function isControl(t: EventTarget | null): boolean {
  return t instanceof Element && t.closest("button, a, input, select, textarea, label") != null;
}

/** Сдвиг, при котором окно (base — его прямоугольник без сдвига) целиком лежит в области area
 *  с зазором EDGE. Окно больше области — прижимаем к левому/верхнему краю: шапка остаётся досягаемой. */
function clampOffset(o: Offset, base: DOMRect, area: DOMRect): Offset {
  const minX = area.left + EDGE - base.left;
  const maxX = area.right - EDGE - base.right;
  const minY = area.top + EDGE - base.top;
  const maxY = area.bottom - EDGE - base.bottom;
  return {
    dx: Math.round(maxX < minX ? minX : Math.min(Math.max(o.dx, minX), maxX)),
    dy: Math.round(maxY < minY ? minY : Math.min(Math.max(o.dy, minY), maxY)),
  };
}

const sameOffset = (a: Offset, b: Offset) => a.dx === b.dx && a.dy === b.dy;

export interface FloatingWindow {
  /** transform для корня окна (undefined — окно на месте по умолчанию или неактивно). */
  style: CSSProperties | undefined;
  dragging: boolean;
  /** Обработчики для шапки-ручки. */
  handle: {
    onPointerDown: (e: ReactPointerEvent<HTMLElement>) => void;
    onDoubleClick: (e: ReactMouseEvent<HTMLElement>) => void;
  };
  /** Сдвиг, который сейчас стоит в DOM. */
  current: () => Offset;
  /** Поставить окно со сдвигом o; commit — запомнить как выбранное место (иначе — только кадр). */
  place: (o: Offset, commit: boolean) => void;
  /** Пока true, изменения размеров не поджимают окно (его тянут или меняют ему размер). */
  hold: (on: boolean) => void;
}

export function useFloatingWindow({
  storageKey,
  elRef,
  getArea,
  active,
}: {
  storageKey: string;
  /** Корень окна. */
  elRef: RefObject<HTMLElement | null>;
  /** Область доски, за которую окно не выходит (стабильная функция — useCallback у вызывающего). */
  getArea: () => Element | null;
  /** Окно открыто и плавает (у карточки — только режим «по центру»). */
  active: boolean;
}): FloatingWindow {
  const [desired, setDesired] = useState<Offset>(() => readOffset(storageKey));
  const [offset, setOffset] = useState<Offset>(desired);
  const [dragging, setDragging] = useState(false);
  // Сдвиг, который стоит в DOM после последнего коммита: из прямоугольника окна минус он — место без сдвига.
  const applied = useRef(offset);
  useLayoutEffect(() => {
    applied.current = offset;
  });
  const busy = useRef(false);

  const measure = useCallback((): { base: DOMRect; area: DOMRect } | null => {
    const el = elRef.current;
    const areaEl = getArea();
    if (!el || !areaEl) return null;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return null;
    const a = applied.current;
    return { base: new DOMRect(r.x - a.dx, r.y - a.dy, r.width, r.height), area: areaEl.getBoundingClientRect() };
  }, [elRef, getArea]);

  // Поджать внутрь области: при открытии, при смене выбранного места и при любом изменении размеров
  // окна (длинный ответ, ширину тянут) или области (окно браузера, панель справа). Равный сдвиг не
  // пишем — без лишних рендеров и петель ResizeObserver.
  useLayoutEffect(() => {
    if (!active) return;
    const fit = () => {
      if (busy.current) return;
      const m = measure();
      if (!m) return;
      const next = clampOffset(desired, m.base, m.area);
      setOffset((cur) => (sameOffset(cur, next) ? cur : next));
    };
    fit();
    const ro = new ResizeObserver(fit);
    if (elRef.current) ro.observe(elRef.current);
    const areaEl = getArea();
    if (areaEl) ro.observe(areaEl);
    window.addEventListener("resize", fit);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", fit);
    };
  }, [active, desired, measure, elRef, getArea]);

  // Пока тянем — курсор «кулак» и без выделения текста по всей странице.
  useEffect(() => {
    if (!dragging) return;
    document.body.classList.add("is-dragging");
    return () => document.body.classList.remove("is-dragging");
  }, [dragging]);

  const onPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLElement>) => {
      if (e.button !== 0 || isControl(e.target)) return;
      const m = measure();
      if (!m) return;
      const handle = e.currentTarget;
      const x0 = e.clientX;
      const y0 = e.clientY;
      const start = applied.current;
      let last: Offset | null = null;
      handle.setPointerCapture(e.pointerId);
      const move = (ev: PointerEvent) => {
        const ddx = ev.clientX - x0;
        const ddy = ev.clientY - y0;
        // Клик и двойной клик по шапке — не перетаскивание.
        if (!last && Math.abs(ddx) + Math.abs(ddy) < 3) return;
        if (!last) {
          busy.current = true;
          setDragging(true);
        }
        last = clampOffset({ dx: start.dx + ddx, dy: start.dy + ddy }, m.base, m.area);
        setOffset(last);
      };
      const end = () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", end);
        handle.removeEventListener("pointercancel", end);
        if (!last) return;
        busy.current = false;
        setDragging(false);
        setDesired(last);
        saveOffset(storageKey, last);
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", end);
      handle.addEventListener("pointercancel", end);
    },
    [measure, storageKey],
  );

  const onDoubleClick = useCallback(
    (e: ReactMouseEvent<HTMLElement>) => {
      if (isControl(e.target)) return;
      setDesired({ dx: 0, dy: 0 });
      saveOffset(storageKey, ZERO);
    },
    [storageKey],
  );

  const place = useCallback(
    (o: Offset, commit: boolean) => {
      const r = { dx: Math.round(o.dx), dy: Math.round(o.dy) };
      setOffset(r);
      if (commit) {
        setDesired(r);
        saveOffset(storageKey, r);
      }
    },
    [storageKey],
  );
  const hold = useCallback((on: boolean) => {
    busy.current = on;
  }, []);
  const current = useCallback(() => applied.current, []);

  const style = active && (offset.dx || offset.dy) ? { transform: `translate(${offset.dx}px, ${offset.dy}px)` } : undefined;
  return { style, dragging, handle: { onPointerDown, onDoubleClick }, current, place, hold };
}
