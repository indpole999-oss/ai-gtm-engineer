import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { API_BASE_URL, AUTH_ENDPOINTS, TOKEN_STORAGE_KEY } from "./api-config";
import { ApiError, apiFetch, getToken, setToken, setWorkspaceId, invalidateSessionRequests } from "./api";
import { createAuthSession, type AuthState, type AuthUser } from "./auth-session";
export type { AuthUser } from "./auth-session";

interface AuthContextValue extends AuthState {
  signIn: (username: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, fullName?: string) => Promise<void>;
  signOut: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function requestLogin(username: string, password: string): Promise<string> {
  const body = new URLSearchParams();
  body.set("grant_type", "password");
  body.set("username", username);
  body.set("password", password);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${AUTH_ENDPOINTS.token}`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
      body,
    });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_BASE_URL}.`);
  }
  const text = await response.text();
  let payload: unknown;
  try { payload = text ? JSON.parse(text) : {}; } catch { payload = text; }
  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload
      ? (payload as { detail: unknown }).detail : undefined;
    throw new ApiError(response.status, typeof detail === "string" ? detail
      : response.status === 401 ? "Incorrect username or password." : `Sign in failed (${response.status}).`, detail);
  }
  const token = payload && typeof payload === "object"
    ? (payload as Record<string, unknown>)["access_token"] : undefined;
  if (typeof token !== "string" || !token.trim()) {
    throw new ApiError(response.status, "The backend did not return an access_token.");
  }
  return token;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const cache = useQueryClient();
  const [state, setState] = useState<AuthState>({ status: "loading", user: null, profileUnavailable: false });
  const session = useMemo(() => createAuthSession({
    getToken, setToken,
    clearWorkspace: () => setWorkspaceId(null),
    clearCache: () => { invalidateSessionRequests(); void cache.cancelQueries(); cache.clear(); },
    profile: () => apiFetch<AuthUser>(AUTH_ENDPOINTS.me),
    publish: setState,
  }), [cache]);

  useEffect(() => {
    void session.refresh();
    return session.dispose;
  }, [session]);

  const signIn = useCallback((username: string, password: string) =>
    session.authenticate(() => requestLogin(username, password)), [session]);
  const signUp = useCallback((email: string, password: string, fullName?: string) =>
    session.authenticate(async () => {
      const payload = await apiFetch<{ access_token?: string }>(AUTH_ENDPOINTS.register, {
        method: "POST", body: JSON.stringify({ email, password, full_name: fullName || null }),
      });
      if (typeof payload?.access_token !== "string" || !payload.access_token.trim()) {
        throw new ApiError(200, "The backend did not return an access_token.");
      }
      return payload.access_token;
    }), [session]);

  useEffect(() => {
    window.addEventListener("gaps:session-expired", session.signOut);
    const syncSession = (event: StorageEvent) => {
      if (event.storageArea !== window.localStorage || (event.key !== null && event.key !== TOKEN_STORAGE_KEY)) return;
      void session.syncSession();
    };
    window.addEventListener("storage", syncSession);
    return () => {
      window.removeEventListener("gaps:session-expired", session.signOut);
      window.removeEventListener("storage", syncSession);
    };
  }, [session]);

  const value = useMemo(() => ({ ...state, signIn, signUp, signOut: session.signOut, refresh: session.refresh }),
    [state, signIn, signUp, session]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export function displayName(user: AuthUser | null): string {
  if (!user) return "Operator";
  for (const key of ["full_name", "name", "username", "email"]) {
    const v = user[key];
    if (typeof v === "string" && v.trim()) return v;
  }
  return "Operator";
}
