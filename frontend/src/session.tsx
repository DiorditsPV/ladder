import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setSessionActive, type AuthUser } from "./api";
import { href } from "./router";

// Режим приложения следует из сессии: нет её — демо (чтение демо-направлений, чек-лист в браузере),
// есть — полный режим по роли (spec 2026-09-11).
type Session = { user: AuthUser | null; ready: boolean; refresh: () => Promise<void>; logout: () => Promise<void> };
const Ctx = createContext<Session>({ user: null, ready: false, refresh: async () => {}, logout: async () => {} });

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const me = await api.me();
      setSessionActive(true);
      setUser(me);
    } catch {
      setSessionActive(false);
      setUser(null);
    } finally {
      setReady(true);
    }
  }, []);
  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setSessionActive(false);
      setUser(null);
      window.location.hash = href.home;
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  const value = useMemo(() => ({ user, ready, refresh, logout }), [user, ready, refresh, logout]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): Session {
  return useContext(Ctx);
}

/** Что можно текущему режиму/роли. Демо — только чек-лист в браузере. */
export function useCan() {
  const role = useSession().user?.role ?? null;
  return {
    demo: role === null,
    editContent: role === "owner" || role === "member",
    syncFiles: role === "owner",
    manageUsers: role === "owner",
  };
}

/** Куда ведёт «← Меню»: главная полного режима или демо-главная. */
export function useHomeHref(): string {
  return useSession().user ? href.home : href.demo;
}
