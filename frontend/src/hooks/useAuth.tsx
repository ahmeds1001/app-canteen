import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { tokens } from "@/api/client";
import { authApi } from "@/api/endpoints";
import type { AuthTokens, User } from "@/api/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  signIn: (data: AuthTokens) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(tokens.access));

  useEffect(() => {
    if (!tokens.access) return;
    authApi
      .me()
      .then(setUser)
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
  }, []);

  const signIn = useCallback((data: AuthTokens) => {
    tokens.set(data.access, data.refresh);
    setUser(data.user);
  }, []);

  const signOut = useCallback(() => {
    tokens.clear();
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, signIn, signOut }), [user, loading, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
