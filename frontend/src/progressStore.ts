import { api } from "./api";
import { useSession } from "./session";
import type { Progress } from "./types";

// Отметки чек-листа: у вошедшего — на сервере, в демо — только в localStorage этого браузера.
export interface ProgressStore {
  load(pool: string): Promise<Record<string, Progress>>;
  set(pool: string, nodeId: string, status: Progress): Promise<void>;
  clear(pool: string, nodeId: string): Promise<void>;
}

const key = (pool: string) => `ladder.progress.${pool}`;

function readLocal(pool: string): Record<string, Progress> {
  try {
    return JSON.parse(localStorage.getItem(key(pool)) || "{}") as Record<string, Progress>;
  } catch {
    return {};
  }
}

function writeLocal(pool: string, value: Record<string, Progress>): void {
  try {
    localStorage.setItem(key(pool), JSON.stringify(value));
  } catch {
    /* приватный режим — отметки живут до перезагрузки */
  }
}

export const localProgress: ProgressStore = {
  load: async (pool) => readLocal(pool),
  set: async (pool, nodeId, status) => {
    const v = readLocal(pool);
    v[nodeId] = status;
    writeLocal(pool, v);
  },
  clear: async (pool, nodeId) => {
    const v = readLocal(pool);
    delete v[nodeId];
    writeLocal(pool, v);
  },
};

export const serverProgress: ProgressStore = {
  load: (pool) => api.progress(pool),
  set: async (_pool, nodeId, status) => {
    await api.setProgress(nodeId, status);
  },
  clear: async (_pool, nodeId) => {
    await api.clearProgress(nodeId);
  },
};

// Модульные синглтоны, а не новый объект на рендер: store стоит в deps эффектов доски.
export function useProgressStore(): ProgressStore {
  return useSession().user ? serverProgress : localProgress;
}

/** Сводка для карточки направления в демо — та же форма, что поле progress у /api/pools. */
export function localSummary(pool: string, total: number) {
  const values = Object.values(readLocal(pool));
  const n = (s: Progress) => values.filter((v) => v === s).length;
  return { known: n("known"), review: n("review"), unknown: n("unknown"), total };
}
