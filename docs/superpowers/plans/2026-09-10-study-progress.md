# Подпроект C: чек-лист разбора — план

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** на доске вне сессии каждая карточка получает статус `known | review | unknown` (свой у каждого пользователя), счётчики колонок/рядов и главной показывают, сколько разобрано; горячие клавиши `1/2/3` ставят статус и ведут к следующей карточке.

**Architecture:** таблица `progress (tenant_id, user_id, node_id, status, updated_at)`; `PUT/DELETE /api/progress/{node_id}`, `GET /api/progress?pool=`, сводка `progress` в `GET /api/pools`. Фронт: `progress` в состоянии доски (вне сессии), точка статуса на карточке, счётчики по `known`, фильтр «только неразобранное», кнопки и хоткеи в drawer, полоска на карточке направления.

**Spec:** `docs/superpowers/specs/2026-09-10-topic-study-pivot-design.md`, подпроект C.

## Global Constraints
- Сессии, оценки, план, отчёт — без изменений; в режиме сессии доска показывает оценки, как сейчас (статусы не показываются, `1–5` = оценка). Вне сессии `1/2/3` = статус, `4/5` не делают ничего.
- Статус — только для видимых нод (`hidden=0`); сводка `total` = число видимых нод пула.
- Изоляция: статусы по `user_id` из `current_user`; гость (`guest`) статусы не ставит — `PUT` 403.
- Комментарии по-русски; `content/` не трогать; i18n-ключи в `en.ts`.
- Режимы: T1 (бэкенд) — субагент + ревью; T2 (фронт) — субагент + ревью; T3 (гейты, smoke-шаг, docs, PR) — инлайн.

### Task 1: бэкенд — таблица, DAL, API, тесты
**Files:** `backend/app/db.py` (`_SCHEMA` + 4 метода), `backend/app/main.py` (3 ручки, `_pool_out`), `backend/tests/test_progress.py`.

Схема (в `_SCHEMA`, после `scores`):
```sql
CREATE TABLE IF NOT EXISTS progress (
    tenant_id  TEXT NOT NULL DEFAULT 'default' REFERENCES tenants(id),
    user_id    TEXT NOT NULL,
    node_id    TEXT NOT NULL,
    status     TEXT NOT NULL,               -- known | review | unknown (чек-лист самоподготовки)
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, user_id, node_id)
);
```
`executescript` с `IF NOT EXISTS` создаёт таблицу на старой БД — миграция не нужна.

DAL (`db.py`, раздел `# --- progress (чек-лист разбора, per-user) ---`):
```python
    PROGRESS_STATUSES = ("known", "review", "unknown")

    def set_progress(self, tenant_id: str, user_id: str, node_id: str, status: str) -> Dict[str, str]:
        """Статус карточки для пользователя (upsert). Валидность status проверяет вызывающий."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO progress (tenant_id, user_id, node_id, status, updated_at) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, user_id, node_id) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
                """,
                (tenant_id, user_id, node_id, status, _now()),
            )
        return {"node_id": node_id, "status": status}

    def clear_progress(self, tenant_id: str, user_id: str, node_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM progress WHERE tenant_id = ? AND user_id = ? AND node_id = ?", (tenant_id, user_id, node_id)
            )
        return cur.rowcount > 0

    def get_progress(self, tenant_id: str, user_id: str, pool: str) -> Dict[str, str]:
        """{node_id: status} по видимым нодам пула — статусы спрятанных нод не отдаём, но и не стираем."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT p.node_id, p.status FROM progress p
                JOIN nodes n ON n.tenant_id = p.tenant_id AND n.id = p.node_id
                WHERE p.tenant_id = ? AND p.user_id = ? AND n.pool = ? AND n.hidden = 0
                """,
                (tenant_id, user_id, pool),
            ).fetchall()
        return {r["node_id"]: r["status"] for r in rows}

    def progress_summary(self, tenant_id: str, user_id: str, pool: str) -> Dict[str, int]:
        """Сводка для главной: сколько known/review/unknown среди видимых нод пула и total = видимых нод."""
        counts = Counter(self.get_progress(tenant_id, user_id, pool).values())
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE tenant_id = ? AND pool = ? AND hidden = 0", (tenant_id, pool)
            ).fetchone()[0]
        return {"known": counts["known"], "review": counts["review"], "unknown": counts["unknown"], "total": total}
```
(`from collections import Counter` в импорты db.py.)

API (`main.py`, раздел `# ---------- progress (чек-лист разбора) ----------` после nodes):
```python
class ProgressIn(BaseModel):
    status: str = Field(pattern="^(known|review|unknown)$")


@app.get("/api/progress")
def get_progress(request: Request, pool: Optional[str] = None, user: dict = Depends(current_user)) -> dict:
    p = _pool_or_404(request, pool)
    return db.get_progress(resolve_tenant(request), user["id"], p.id)


@app.put("/api/progress/{node_id}")
def set_progress(node_id: str, body: ProgressIn, request: Request, user: dict = Depends(require_member)) -> dict:
    """Статус карточки для текущего пользователя. Гость (по ссылке) статусы не ставит — 403 из require_member."""
    tenant = resolve_tenant(request)
    if db.get_node(tenant, node_id) is None:
        raise HTTPException(status_code=404, detail=f"node '{node_id}' not found")
    return db.set_progress(tenant, user["id"], node_id, body.status)


@app.delete("/api/progress/{node_id}")
def clear_progress(node_id: str, request: Request, user: dict = Depends(require_member)) -> dict:
    return {"cleared": db.clear_progress(resolve_tenant(request), user["id"], node_id)}
```
`_pool_out(request, p, user)` → добавить `"progress": db.progress_summary(tenant, user["id"], p.id)`; три вызова (`get_pools`, `create_pool`, `update_pool`) передают `_user`. Проверь, как `require_member` ведёт себя с гостем (`allow_guest` по умолчанию False → 403) — это и есть требуемое поведение.

Тесты `test_progress.py` (образец фикстур — `test_levels.py`): DAL — set/upsert/clear, изоляция двух `user_id`, `get_progress` не отдаёт статус скрытой ноды, `progress_summary` считает total по видимым; API — `PUT` на чужой id → 404, `PUT` с `status: "meh"` → 422, `GET /api/progress?pool=data-engineer` возвращает выставленное, `GET /api/pools` содержит `progress.total == counts.nodes` для DE, после `DELETE` статус исчез. В конце тесты чистят за собой (`DELETE`).

Гейт: `pytest -q` (все + новые), коммит `feat(progress): чек-лист разбора — таблица progress, PUT/DELETE/GET /api/progress, сводка в /api/pools`.

### Task 2: фронт — статус на доске, drawer, хоткеи, фильтр, главная
**Files:** `types.ts` (`Progress`, `PoolConfig.progress?`), `api.ts` (`progress(pool)`, `setProgress`, `clearProgress`), `components/QuestionNode.tsx` (`status?` в data, точка `.qnode__status` с `data-status`), `components/DetailDrawer.tsx` (`status`, `onStatus`; три кнопки «Знаю (1)» / «Повторить (2)» / «Не знаю (3)» — вне сессии вместо блока оценки), `pages/BoardPage.tsx`, `pages/HomePage.tsx`, `styles.css`, `i18n/en.ts`.

BoardPage:
- `const [progress, setProgress] = useState<Record<string, Progress>>({})`; вне сессии — `api.progress(pool.id)` при загрузке графа; `setStatus(nodeId, status)`: optimistic update + `api.setProgress`, при ошибке откат; повтор той же клавиши на карточке с тем же статусом — `clearProgress` (снять).
- `buildNodes(...)` получает `progress` и кладёт `status` в data карточки; счётчики `done` у `BlockGroupNode`/`SubHeadNode`/рядов: в сессии — как сейчас (оценки), вне сессии — число `known`.
- Хоткеи (~667): `if (session) { 1–5 → applyScore } else if (e.key in "123") { setStatus(currentId, ["known","review","unknown"][k-1]); переход к следующей карточке в порядке матрицы (следующая в колонке, затем первая следующей колонки — по `placement.order`) }`.
- Фильтр: тумблер «только неразобранное» (`unresolvedOnly`) рядом с «только неоценённые» (показывать в панели вне сессии); предикат `dimmed` — `unresolvedOnly && progress[n.id] === "known"`.
- HUD/toolbar вне сессии: `разобрано K/N` вместо `scored/graph.length` (строка ~1318).
- HomePage: если `p.progress && p.progress.total > 0` — полоска `poolcard__progress` (ширина `known/total`) и подпись `t("разобрано {k} из {n}")`.
- `QuestionNode`: `<span className="qnode__status" data-status={status} />` слева от заголовка; CSS: known — `#16a34a`, review — `#d97706`, unknown — `#dc2626`, без статуса — пустой кружок `var(--border-strong)`.
- i18n: «Знаю», «Повторить», «Не знаю», «только неразобранное», «разобрано {k} из {n}», «Разобрано».

Гейты: `npm run build`, `npm run i18n:check`, Playwright-проверка (свежая dev-БД): открыть DE-доску вне сессии, кликнуть карточку, нажать `1` → `.qnode__status[data-status="known"]` = 1, счётчик колонки вырос, `GET /api/pools` → `progress.known == 1`. Коммит `feat(progress): статусы на доске, drawer и хоткеи 1/2/3, фильтр «только неразобранное», прогресс на главной`.

### Task 3 (inline): smoke-шаг, docs, PR
- `frontend/smoke.mjs`: после шага с доской DE вне сессии — шаг «чек-лист»: клик по карточке, `1`, ждать `.qnode__status[data-status="known"]`, проверить `.bgroup__count` изменился; в конце — `DELETE /api/progress/<id>` через `page.request` или оставить (свежая БД).
- `CLAUDE.md`/`AGENTS.md`: абзац про чек-лист (таблица `progress`, хоткеи, что в сессии не показывается). README: одна фраза.
- Гейты ветки: pytest, build, i18n, smoke 54+1 на свежей БД, `git diff dev -- content/` пуст. Финальное ревью ветки → волна правок → PR в `dev`.
