import type {
  Block,
  Difficulty,
  GraphResponse,
  ImportResult,
  PoolConfig,
  Progress,
} from "./types";

// question-management: правка/создание вопроса банка (бэкенд пишет в БД, не в content/*.md).
export interface NodeUpdate {
  title?: string;
  difficulty?: Difficulty;
  question?: string;
  answer?: string;
}

export interface NodeCreate {
  pool: string;
  block: Block;
  topic: string;
  difficulty: Difficulty;
  kind: "question" | "task";
  title?: string;
  question: string;
  answer: string;
  tags: string[];
}

// auth-identity (#36): пользователь сессии (без password_hash).
export interface AuthUser {
  id: string;
  email: string;
  role: "owner" | "member" | "viewer";
  tenant_id: string;
}

// Аккаунт полного режима (страница «Люди», owner): GET /api/users.
export interface AccountUser {
  id: string;
  email: string;
  role: AuthUser["role"];
  tenant_id: string;
  created_at?: string;
}

// В dev /api проксируется Vite на :8000; в прод тот же origin (раздаёт FastAPI).
const BASE = "/api";

let sessionActive = false;
/** Сессия подтверждена /api/auth/me: только тогда 401 означает «протухла» → перезагрузка. */
export function setSessionActive(on: boolean): void {
  sessionActive = on;
}

// auth-hardening (#40): 401 в середине живой сессии (протухла/инвалидирована) → перезагрузка,
// приложение откроется заново уже в демо-режиме. В демо (сессии нет) 401 значит «нельзя»,
// а не «протухло» — перезагрузка там была бы петлёй (spec 2026-09-11). skipAuthReload — для
// auth-проб (login/me), которые сами штатно отдают 401 (неверный пароль / нет сессии).
async function json<T>(res: Response, opts?: { skipAuthReload?: boolean }): Promise<T> {
  if (res.status === 401 && sessionActive && !opts?.skipAuthReload) {
    window.location.reload();
    throw new Error("session expired");
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// pool-blocks-editor: колонка направления из формы. id — только у существующих (сервер сохраняет
// их как есть), у новых id генерится из названия; weight из UI не правится.
export interface BlockDraft {
  uid?: string; // клиентский ключ ряда в редакторе; в запрос не попадает
  id?: string;
  label: string;
  color: string;
  subblocks?: { id?: string; label: string }[];
}

// pool-levels: уровень сложности из формы. id — только у существующих (сервер сохраняет как есть),
// у новых id генерится из label.
export interface LevelDraft {
  uid?: string; // клиентский ключ ряда в редакторе; в запрос не попадает
  id?: string;
  label: string;
}

// Отчёт POST /api/pools/sync: засев (по умолчанию) или явное обновление пресета из content/ (update=true);
// dry_run — тот же прогон на копии БД, живая не меняется. nodes_changed — новые и реально переписанные карточки.
export interface SyncReport {
  mode: "seed" | "update";
  dry_run: boolean;
  created: string[];
  updated: string[];
  config_changed: string[];
  nodes_upserted: number;
  nodes_changed: number;
  skipped: number;
  hidden: string[];
  conflicts: string[];
  errors: { file: string; error: string }[];
}

export const api = {
  pools: () => fetch(`${BASE}/pools`).then(json<PoolConfig[]>),
  // pool-crud: направления живут в БД; ровно одно из preset (существующее направление: колонки +
  // вопросы копируются) / blocks (свои колонки, без вопросов).
  createPool: (data: { label: string; description?: string; preset?: string; blocks?: BlockDraft[]; levels?: LevelDraft[] }) =>
    fetch(`${BASE}/pools`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(json<PoolConfig>),
  // blocks: колонка вне списка удаляется вместе с вопросами, под-колонка — вопросы остаются в колонке.
  updatePool: (id: string, fields: { label?: string; description?: string; blocks?: BlockDraft[]; levels?: LevelDraft[] }) =>
    fetch(`${BASE}/pools/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    }).then(json<PoolConfig>),
  // sync-pools: content/ → БД без рестарта (новые пулы + upsert файловых нод + скрытие исчезнувших).
  // Явное обновление одного пресета из файлов; dryRun — предпросмотр без записи.
  syncPool: (id: string, dryRun: boolean) =>
    fetch(`${BASE}/pools/sync?pool=${encodeURIComponent(id)}&update=true${dryRun ? "&dry_run=true" : ""}`, {
      method: "POST",
    }).then(json<SyncReport>),
  deletePool: (id: string) =>
    fetch(`${BASE}/pools/${encodeURIComponent(id)}`, { method: "DELETE" }).then(
      json<{ deleted: string; nodes_removed: number }>,
    ),
  graph: (pool: string) =>
    fetch(`${BASE}/graph?pool=${encodeURIComponent(pool)}`).then(json<GraphResponse>),
  importFile: (pool: string, filename: string, content: string) =>
    fetch(`${BASE}/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pool, filename, content }),
    }).then(json<ImportResult>),
  // question-management CRUD банка вопросов (источник правды — БД на бэкенде).
  createNode: (data: NodeCreate) =>
    fetch(`${BASE}/nodes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(json<{ id: string; block: string; title: string }>),
  updateNode: (id: string, fields: NodeUpdate) =>
    fetch(`${BASE}/nodes/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    }).then(json<{ updated: string }>),
  deleteNode: (id: string) =>
    fetch(`${BASE}/nodes/${encodeURIComponent(id)}`, { method: "DELETE" }).then(
      json<{ deleted: string }>,
    ),
  // auth-identity (#36): server-side сессия в HttpOnly-cookie. credentials:"include" —
  // чтобы cookie слалась и в dev (Vite-прокси), и в прод (тот же origin).
  login: (email: string, password: string) =>
    fetch(`${BASE}/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }).then((res) => json<AuthUser>(res, { skipAuthReload: true })),
  logout: () =>
    fetch(`${BASE}/auth/logout`, { method: "POST", credentials: "include" }).then(
      json<{ ok: boolean }>,
    ),
  me: () =>
    fetch(`${BASE}/auth/me`, { credentials: "include" }).then((res) =>
      json<AuthUser>(res, { skipAuthReload: true }),
    ),
  // Смена своего пароля (любой вошедший). Неверный текущий — 403 (не 401: 401 перезагрузил бы
  // страницу), короткий новый — 422; остальные сессии пользователя сервер отзывает.
  changePassword: async (current: string, next: string): Promise<"ok" | "wrong-current" | "too-short"> => {
    const res = await fetch(`${BASE}/auth/password`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: current, new_password: next }),
    });
    if (res.status === 403) return "wrong-current";
    if (res.status === 422) return "too-short";
    await json<{ ok: boolean }>(res);
    return "ok";
  },
  // Аккаунты (owner): без password сервер заводит одноразовый и отдаёт его в ответе один раз.
  users: () => fetch(`${BASE}/users`).then(json<AccountUser[]>),
  createUser: (email: string) =>
    fetch(`${BASE}/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    }).then(json<AccountUser & { password: string }>),
  resetUserPassword: (id: string) =>
    fetch(`${BASE}/users/${encodeURIComponent(id)}/password`, { method: "POST" }).then(json<{ id: string; password: string }>),
  deleteUser: (id: string) =>
    fetch(`${BASE}/users/${encodeURIComponent(id)}`, { method: "DELETE" }).then(json<{ deleted: string }>),
  // Чек-лист разбора (per-user): статус карточки known|review|unknown.
  progress: (pool: string) =>
    fetch(`${BASE}/progress?pool=${encodeURIComponent(pool)}`).then(json<Record<string, Progress>>),
  setProgress: (nodeId: string, status: Progress) =>
    fetch(`${BASE}/progress/${encodeURIComponent(nodeId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }).then(json<{ node_id: string; status: Progress }>),
  clearProgress: (nodeId: string) =>
    fetch(`${BASE}/progress/${encodeURIComponent(nodeId)}`, { method: "DELETE" }).then(
      json<{ cleared: boolean }>,
    ),
};
