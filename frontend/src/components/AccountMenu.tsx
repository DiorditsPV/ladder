import { useEffect, useState } from "react";
import { useT } from "../i18n";
import { href } from "../router";
import { useSession } from "../session";
import { ChangePasswordModal } from "./ChangePasswordModal";

// Аккаунт на главной полного режима: почта → «Сменить пароль» · «Люди» (owner) · «Выйти».
// Закрытие кликом мимо и Esc — как меню ••• на главной.
export function AccountMenu() {
  const t = useT();
  const { user, logout } = useSession();
  const [open, setOpen] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("click", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  if (!user) return null;
  return (
    <div className="account">
      <button className="account__btn iconbtn btn--quiet" aria-haspopup="menu" aria-expanded={open}
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}>
        {user.email}
      </button>
      {open && (
        <div className="account__menu" role="menu" onClick={(e) => e.stopPropagation()}>
          <button className="account__password" role="menuitem" onClick={() => { setOpen(false); setPwOpen(true); }}>{t("Сменить пароль")}</button>
          {user.role === "owner" && (
            <a className="account__people" role="menuitem" href={href.people} onClick={() => setOpen(false)}>{t("Люди")}</a>
          )}
          <button className="account__logout" role="menuitem" onClick={() => { setOpen(false); void logout(); }}>{t("Выйти")}</button>
        </div>
      )}
      {pwOpen && <ChangePasswordModal onClose={() => setPwOpen(false)} />}
    </div>
  );
}
