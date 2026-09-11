import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { useT } from "../i18n";

// Смена своего пароля (главная полного режима и панель ⚙ доски). Оверлей и Esc — как в UploadModal,
// классы upload-modal* переиспользуются. После смены остальные устройства выходят из аккаунта.
export function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const t = useT();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopImmediatePropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, { capture: true });
    return () => window.removeEventListener("keydown", onKey, { capture: true });
  }, [onClose]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (next.length < 8) return setError(t("Новый пароль — не короче 8 символов"));
    if (next !== repeat) return setError(t("Пароли не совпадают"));
    setBusy(true);
    try {
      const r = await api.changePassword(current, next);
      if (r === "wrong-current") setError(t("Текущий пароль неверный"));
      else if (r === "too-short") setError(t("Новый пароль — не короче 8 символов"));
      else setDone(true);
    } catch {
      setError(t("Не удалось сменить пароль"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="upload-modal" onClick={onClose}>
      <form className="upload-modal__card pwmodal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <div className="upload-modal__head">
          <strong>{t("Сменить пароль")}</strong>
          <button type="button" className="upload-modal__close" onClick={onClose} title={t("Закрыть (Esc)")}>✕</button>
        </div>
        {done ? (
          <p className="pwmodal__ok">{t("Пароль изменён. Остальные устройства вышли из аккаунта.")}</p>
        ) : (
          <>
            <input className="pwmodal__current" type="password" autoComplete="current-password" placeholder={t("Текущий пароль")} value={current} onChange={(e) => setCurrent(e.target.value)} autoFocus />
            <input className="pwmodal__new" type="password" autoComplete="new-password" placeholder={t("Новый пароль")} value={next} onChange={(e) => setNext(e.target.value)} />
            <input className="pwmodal__repeat" type="password" autoComplete="new-password" placeholder={t("Повторите новый пароль")} value={repeat} onChange={(e) => setRepeat(e.target.value)} />
            {error && <div className="pwmodal__error">{error}</div>}
            <button className="btn--primary pwmodal__submit" type="submit" disabled={busy || !current || !next}>{t("Сменить")}</button>
          </>
        )}
      </form>
    </div>
  );
}
