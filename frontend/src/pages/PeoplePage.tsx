import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type AccountUser } from "../api";
import { useT } from "../i18n";
import { useSession } from "../session";
import { PageShell } from "./PageShell";

// «Люди» (owner): аккаунты полного режима. Пароль показывается один раз — после заведения или сброса.
export function PeoplePage() {
  const t = useT();
  const { user } = useSession();
  const [users, setUsers] = useState<AccountUser[]>([]);
  const [email, setEmail] = useState("");
  const [issued, setIssued] = useState<{ email: string; password: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api.users().then(setUsers).catch(() => setError(t("Не удалось загрузить список"))), [t]);
  useEffect(() => { void load(); }, [load]);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const value = email.trim();
    if (!value) return;
    try {
      const created = await api.createUser(value);
      setIssued({ email: created.email, password: created.password });
      setEmail("");
      void load();
    } catch (err) {
      setError(String(err).includes("409") ? t("Такой аккаунт уже есть") : t("Не удалось добавить"));
    }
  };
  const reset = async (u: AccountUser) => {
    setError(null);
    try {
      const r = await api.resetUserPassword(u.id);
      setIssued({ email: u.email, password: r.password });
    } catch {
      setError(t("Не удалось сбросить пароль"));
    }
  };
  const remove = async (u: AccountUser) => {
    if (!window.confirm(t("Удалить аккаунт {email} вместе с его чек-листом?", { email: u.email }))) return;
    setError(null);
    try {
      await api.deleteUser(u.id);
      void load();
    } catch {
      setError(t("Не удалось удалить аккаунт"));
    }
  };
  const roleLabel = (r: AccountUser["role"]) => (r === "owner" ? t("владелец") : r === "member" ? t("редактор") : t("разбор"));

  return (
    <PageShell title={t("Люди")}>
      <form className="people__add" onSubmit={add}>
        <input className="people__email" type="email" placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <button className="btn--primary people__submit" type="submit" disabled={!email.trim()}>{t("Добавить")}</button>
      </form>
      {issued && (
        <div className="people__issued" role="status">
          <span>{t("Пароль для {email} — показывается один раз:", { email: issued.email })}</span>
          <code className="people__password">{issued.password}</code>
          <button className="iconbtn" onClick={() => void navigator.clipboard?.writeText(issued.password)}>{t("Скопировать")}</button>
          <button className="iconbtn btn--quiet" onClick={() => setIssued(null)}>{t("Скрыть")}</button>
        </div>
      )}
      {error && <div className="errbar">{error}</div>}
      <table className="people__table">
        <thead>
          <tr><th>{t("Почта")}</th><th>{t("Доступ")}</th><th>{t("Заведён")}</th><th /></tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} data-email={u.email}>
              <td>{u.email}</td>
              <td>{roleLabel(u.role)}</td>
              <td>{u.created_at?.slice(0, 10) ?? ""}</td>
              <td className="people__actions">
                {u.id !== user?.id && (
                  <>
                    <button className="iconbtn people__reset" onClick={() => void reset(u)}>{t("Сбросить пароль")}</button>
                    <button className="iconbtn people__delete" onClick={() => void remove(u)}>{t("Удалить")}</button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </PageShell>
  );
}
