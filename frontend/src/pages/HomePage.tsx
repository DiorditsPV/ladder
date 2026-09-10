import { ArrowRight, BookOpen, CircleHelp, Ellipsis } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type AuthUser } from "../api";
import { LangSwitch } from "../components/LangSwitch";
import { PoolFormModal } from "../components/PoolFormModal";
import { nWord, useT } from "../i18n";
import { poolIcon } from "../poolIcons";
import { href } from "../router";
import type { PoolConfig } from "../types";

type PoolModal = { mode: "create" } | { mode: "edit"; pool: PoolConfig } | null;

// Главное меню: направления как входы на доски. Карточка направления: название, описание,
// статистика, полоска чек-листа, нейтральные чипы колонок, primary «Открыть доску →»
// и «Банк вопросов», меню ••• (редактировать/дублировать/обновить из файлов/удалить).
// Пулов может не быть вовсе (content/ без pool.yaml) — говорим об этом, а не рисуем пустоту.
// onChanged — направления создаются/правятся/удаляются здесь же (pool-crud); список живёт в Router.
export function HomePage({
  pools,
  notice,
  onChanged,
}: { pools: PoolConfig[]; notice?: string; onChanged: () => void }) {
  const t = useT();
  const [modal, setModal] = useState<PoolModal>(null);
  const [menuFor, setMenuFor] = useState<string | null>(null);
  // Сводка «Обновить из файлов» — полоской над списком, как notice; пункт меню виден только owner'у
  // (ручка /api/pools/sync — owner-only).
  const [note, setNote] = useState<string | null>(null);
  const [role, setRole] = useState<AuthUser["role"] | null>(null);
  useEffect(() => {
    api.me().then((me) => setRole(me.role)).catch(() => setRole(null));
  }, []);
  // Меню ••• закрывается кликом мимо и Esc — как обычный dropdown.
  useEffect(() => {
    if (!menuFor) return;
    const close = () => setMenuFor(null);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("click", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuFor]);

  const remove = async (p: PoolConfig) => {
    const ok = window.confirm(
      t("Удалить направление «{label}»? Вопросы ({nodes}) будут удалены безвозвратно.", {
        label: p.label,
        nodes: p.counts?.nodes ?? 0,
      }),
    );
    if (!ok) return;
    try {
      await api.deletePool(p.id);
      onChanged();
    } catch {
      alert(t("Не удалось удалить направление"));
    }
  };

  // «Дублировать» = создать из пресета p: сервер копирует разделы и вопросы, id — из названия «… (копия)».
  const duplicate = async (p: PoolConfig) => {
    try {
      await api.createPool({ label: t("{label} (копия)", { label: p.label }), description: p.description, preset: p.id });
      onChanged();
    } catch {
      alert(t("Не удалось дублировать направление"));
    }
  };

  // «Обновить из файлов» — content/ → БД без рестарта: новые направления, правки конфигов и seed-нод.
  // Пользовательские вопросы (source=user) файлы не трогают; исчезнувшие seed-ноды прячутся.
  const syncFromFiles = async () => {
    try {
      const r = await api.syncPools();
      let text = t("Обновлено из файлов: направлений {p}, вопросов {n}, скрыто {h}, конфликтов {c}", {
        p: r.created.length + r.updated.length,
        n: r.nodes_upserted,
        h: r.hidden.length,
        c: r.conflicts.length,
      });
      if (r.errors.length) {
        text += ". " + t("Ошибок импорта: {n}; первая — {file}: {error}", { n: r.errors.length, file: r.errors[0].file, error: r.errors[0].error });
      }
      setNote(text);
      onChanged();
    } catch {
      alert(t("Не удалось обновить из файлов"));
    }
  };

  // Статистика направления с правильными формами числа: «61 вопрос».
  const questions = (n: number) => `${n} ${nWord(n, ["вопрос", "вопроса", "вопросов"], ["question", "questions"])}`;
  // Иконки — только outline Lucide, единый stroke-width: они усиливают иерархию, а не спорят с CTA.
  const ICON = { strokeWidth: 1.75 } as const;

  return (
    <div className="page home">
      <header className="pageshell">
        <h1 className="pageshell__title">{t("Ladder · разбор тем по ступеням")}</h1>
        <div className="pageshell__actions">
          <LangSwitch />
        </div>
      </header>
      <main className="page__body">
        {notice && <div className="errbar">{notice}</div>}
        {note && <div className="errbar errbar--ok">{note}</div>}

        <div className="home__head">
          <h2 className="home__h2">{t("Направления")}</h2>
          {/* Новое направление — из пресета (копия колонок и вопросов) или со своими колонками,
              поэтому кнопка есть и без единого пула. Тихая: не спорит с карточками. */}
          <button className="home__add iconbtn btn--quiet" onClick={() => setModal({ mode: "create" })}>
            {t("+ Новое направление")}
          </button>
        </div>
        {pools.length === 0 && (
          <p className="muted">{t("Нет ни одного направления: создайте первое кнопкой «+ Новое направление» или положите каталог с `pool.yaml` в `content/`.")}</p>
        )}
        <div className="home__pools">
          {pools.map((p) => {
            const { Icon, tint } = poolIcon(p.id);
            return (
            <div key={p.id} className={`poolcard poolcard--${tint}`} data-pool={p.id}>
              {/* Меню направления лежит над «растяжкой» .poolcard__label::after (z-index), иначе клик уводит на доску. */}
              <button
                className="poolcard__menu iconbtn"
                aria-label={t("Меню направления")}
                aria-haspopup="menu"
                aria-expanded={menuFor === p.id}
                onClick={(e) => {
                  e.stopPropagation();
                  setMenuFor((cur) => (cur === p.id ? null : p.id));
                }}
              >
                <Ellipsis size={18} {...ICON} />
              </button>
              {menuFor === p.id && (
                <div className="poolcard__dropdown" role="menu" onClick={(e) => e.stopPropagation()}>
                  <button className="poolcard__edit" role="menuitem" onClick={() => { setMenuFor(null); setModal({ mode: "edit", pool: p }); }}>
                    {t("Редактировать")}
                  </button>
                  <button className="poolcard__dup" role="menuitem" onClick={() => { setMenuFor(null); duplicate(p); }}>
                    {t("Дублировать")}
                  </button>
                  {role === "owner" && (
                    <button className="poolcard__sync" role="menuitem" onClick={() => { setMenuFor(null); syncFromFiles(); }}>
                      {t("Обновить из файлов")}
                    </button>
                  )}
                  <div className="poolcard__dropdown-sep" role="separator" />
                  <button className="poolcard__delete" role="menuitem" onClick={() => { setMenuFor(null); remove(p); }}>
                    {t("Удалить")}
                  </button>
                </div>
              )}
              <div className="poolcard__head">
                <span className={`poolcard__icon poolcard__icon--${tint}`} aria-hidden="true">
                  <Icon size={24} {...ICON} />
                </span>
                <div className="poolcard__titles">
                  {/* Ссылка-«растяжка»: её ::after накрывает всю карточку — клик в любом месте открывает доску. */}
                  <a className="poolcard__label" href={href.board(p.id)}>{p.label}</a>
                  {p.description && <div className="poolcard__desc">{p.description}</div>}
                </div>
              </div>
              <div className="poolcard__meta">
                <span className="poolcard__stat"><CircleHelp size={16} strokeWidth={2} aria-hidden="true" />{questions(p.counts?.nodes ?? 0)}</span>
              </div>
              {/* Чек-лист разбора: доля «знаю» карточек направления (per-user). */}
              {p.progress && p.progress.total > 0 && (
                <div className="poolcard__progress">
                  <div className="poolcard__progress-track">
                    <div
                      className="poolcard__progress-fill"
                      style={{ width: `${Math.round((p.progress.known / p.progress.total) * 100)}%` }}
                    />
                  </div>
                  <span className="poolcard__progress-label">
                    {t("разобрано {k} из {n}", { k: p.progress.known, n: p.progress.total })}
                  </span>
                </div>
              )}
              <div className="poolcard__blocks">
                {p.blocks.map((b) => (
                  <span key={b.id} className="poolcard__block">{b.label}</span>
                ))}
              </div>
              {/* Действия лежат над «растяжкой»; margin-top:auto прижимает их к низу — карточки в ряду одной высоты. */}
              <div className="poolcard__actions">
                <a className="poolcard__open btn--primary" href={href.board(p.id)}>
                  {t("Открыть доску")}
                  <ArrowRight size={16} {...ICON} aria-hidden="true" />
                </a>
                <a className="poolcard__start" href={href.bank(p.id)}>
                  <BookOpen size={15} strokeWidth={2} aria-hidden="true" />
                  {t("Банк вопросов")}
                </a>
              </div>
            </div>
            );
          })}
        </div>
        {modal && (
          <PoolFormModal
            mode={modal.mode}
            pools={pools}
            pool={modal.mode === "edit" ? modal.pool : undefined}
            onClose={() => setModal(null)}
            onSaved={() => {
              setModal(null);
              onChanged();
            }}
          />
        )}

      </main>
    </div>
  );
}
