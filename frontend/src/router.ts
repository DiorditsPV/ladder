import { useEffect, useState } from "react";

// Свой hash-роутер: адреса вида #/board/data-engineer. Без зависимости —
// нам нужны три маршрута, глубокие ссылки и F5; history API не нужен
// (бэкенд раздаёт статику одним index.html, hash его не трогает).

export type Route =
  | { name: "home" }
  | { name: "board"; pool: string }
  | { name: "bank"; pool: string };

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#/, "");
  const [pathPart] = raw.split("?");
  const segs = pathPart.split("/").filter(Boolean);
  if (segs.length === 0) return { name: "home" };
  if (segs[0] === "board" && segs[1]) return { name: "board", pool: decodeURIComponent(segs[1]) };
  if (segs[0] === "bank" && segs[1]) return { name: "bank", pool: decodeURIComponent(segs[1]) };
  return { name: "home" }; // неизвестный путь → меню
}

export const href = {
  home: "#/",
  board: (pool: string) => `#/board/${encodeURIComponent(pool)}`,
  bank: (pool: string) => `#/bank/${encodeURIComponent(pool)}`,
};

export function navigate(to: string): void {
  window.location.hash = to;
}

/** Текущий маршрут; перерисовка на hashchange. */
export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
