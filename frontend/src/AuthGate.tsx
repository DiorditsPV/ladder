import Router from "./Router.tsx";
import { SessionProvider, useSession } from "./session";

// Гейт больше не требует входа: без сессии — демо-режим, вход — по #/login (spec 2026-09-11).
// Router рендерится после первичной проверки сессии (/api/auth/me): режим известен до первых запросов.
function Gate() {
  const { ready } = useSession();
  if (!ready) return null;
  return <Router />;
}

export function AuthGate() {
  return (
    <SessionProvider>
      <Gate />
    </SessionProvider>
  );
}
