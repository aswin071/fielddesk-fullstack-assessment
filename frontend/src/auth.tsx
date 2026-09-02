import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { API_BASE, apiRequest, getAccessToken, setAccessToken } from "./api";
import type { Session } from "./types";

interface AuthContextValue {
  session: Session | null;
  loading: boolean;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [tokenVersion, setTokenVersion] = useState(0);

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "include" })
      .then(async (response) => {
        if (!response.ok) return null;
        const body = (await response.json()) as { data: { accessToken: string } };
        setAccessToken(body.data.accessToken);
        return apiRequest<Session>("/auth/me", { retryAuth: false });
      })
      .then((restored) => {
        if (active && restored) {
          setSession(restored);
          setTokenVersion((value) => value + 1);
        }
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      loading,
      token: tokenVersion >= 0 ? getAccessToken() : null,
      login: async (email, password) => {
        const result = await apiRequest<Session & { accessToken: string }>("/auth/login", {
          method: "POST",
          body: { email, password },
          retryAuth: false,
        });
        setAccessToken(result.accessToken);
        const currentSession: Session = {
          user: result.user,
          role: result.role,
          organisation: result.organisation,
        };
        setSession(currentSession);
        setTokenVersion((value) => value + 1);
      },
      logout: async () => {
        try {
          await apiRequest("/auth/logout", { method: "POST" });
        } finally {
          setAccessToken(null);
          setSession(null);
          setTokenVersion((value) => value + 1);
          window.location.assign("/login");
        }
      },
    }),
    [loading, session, tokenVersion],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// Provider and hook intentionally share this small module.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
