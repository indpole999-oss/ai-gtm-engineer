import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { API_BASE_URL, AUTH_ENDPOINTS } from "./api-config";
import { ApiError, apiFetch, getToken, setToken } from "./api";

export type AuthUser = Record<string, unknown> & { email?: string; username?: string; id?: string | number };

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  /** True when /auth/me is unavailable (404/405) — we trust the stored token instead. */
  profileUnavailable: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, fullName?: string) => Promise<void>;
  signOut: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [profileUnavailable, setProfileUnavailable] = useState(false);

  const loadProfile = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setStatus("anonymous");
      return;
    }
    try {
      const me = await apiFetch<AuthUser>(AUTH_ENDPOINTS.me);
      setUser(me ?? null);
      setProfileUnavailable(false);
      setStatus("authenticated");
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        setToken(null);
        setUser(null);
        setStatus("anonymous");
        return;
      }
      // Endpoint missing or backend unreachable: keep the session, flag it.
      setProfileUnavailable(true);
      setUser(null);
      setStatus("authenticated");
    }
  }, []);

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  const signIn = useCallback(
    async (username: string, password: string) => {
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
      try {
        payload = text ? JSON.parse(text) : {};
      } catch {
        payload = text;
      }

      if (!response.ok) {
        const detail =
          payload && typeof payload === "object" && "detail" in payload
            ? (payload as { detail: unknown }).detail
            : undefined;
        throw new ApiError(
          response.status,
          typeof detail === "string"
            ? detail
            : response.status === 401
              ? "Incorrect username or password."
              : `Sign in failed (${response.status}).`,
          detail,
        );
      }

      const token =
        payload && typeof payload === "object"
          ? ((payload as Record<string, unknown>)["access_token"] as string | undefined)
          : undefined;
      if (!token) {
        throw new ApiError(response.status, "The backend did not return an access_token.");
      }
      setToken(token);
      await loadProfile();
    },
    [loadProfile],
  );

  const signUp = useCallback(
    async (email: string, password: string, fullName?: string) => {
      const payload = await apiFetch<{ access_token?: string }>(AUTH_ENDPOINTS.register, {
        method: "POST",
        body: JSON.stringify({ email, password, full_name: fullName || null }),
      });
      if (!payload?.access_token) {
        throw new ApiError(200, "The backend did not return an access_token.");
      }
      setToken(payload.access_token);
      await loadProfile();
    },
    [loadProfile],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
    setProfileUnavailable(false);
    setStatus("anonymous");
  }, []);

  const value = useMemo(
    () => ({ status, user, profileUnavailable, signIn, signUp, signOut, refresh: loadProfile }),
    [status, user, profileUnavailable, signIn, signUp, signOut, loadProfile],
  );

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
