export type AuthUser = Record<string, unknown> & { email?: string; username?: string; id?: string | number };
export type AuthState = {
  status: "loading" | "authenticated" | "anonymous" | "unavailable";
  user: AuthUser | null;
  profileUnavailable: boolean;
};

type Dependencies = {
  getToken: () => string | null;
  setToken: (token: string | null) => void;
  clearWorkspace: () => void;
  clearCache: () => void;
  profile: () => Promise<unknown>;
  publish: (state: AuthState) => void;
};

/** A generation fences every asynchronous identity operation, including logins. */
export function createAuthSession(deps: Dependencies) {
  let generation = 0;
  const superseded = () => new DOMException("Sign-in changed. Please try again.", "AbortError");
  const publish = (status: AuthState["status"], user: AuthUser | null = null) => {
    deps.publish({ status, user, profileUnavailable: status === "unavailable" });
  };
  const hide = () => {
    deps.clearCache();
    publish("loading");
  };
  function signOut() {
    generation++;
    deps.setToken(null);
    deps.clearWorkspace();
    deps.clearCache();
    publish("anonymous");
  }
  async function verify(epoch: number) {
    const token = deps.getToken();
    if (!token) {
      if (epoch === generation) {
        deps.clearWorkspace();
        publish("anonymous");
      }
      return;
    }
    const current = () => epoch === generation && deps.getToken() === token;
    try {
      const value = await deps.profile();
      if (!current()) throw superseded();
      if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Account identity was not verified.");
      const user = value as AuthUser;
      if (!(typeof user.id === "string" && user.id.trim() || typeof user.id === "number" && Number.isFinite(user.id))
          || typeof user.email !== "string" || !user.email.trim()) {
        throw new Error("Account identity was not verified.");
      }
      publish("authenticated", user);
    } catch (error) {
      if (!current()) throw superseded();
      const status = (error as { status?: number } | null)?.status;
      if (status === 401 || status === 403) signOut();
      else {
        deps.clearCache();
        publish("unavailable");
      }
      throw error;
    }
  }
  async function refresh() {
    const epoch = ++generation;
    hide();
    try { await verify(epoch); } catch { /* State contains the recoverable failure. */ }
  }
  async function authenticate(request: () => Promise<string>) {
    const epoch = ++generation;
    deps.setToken(null);
    deps.clearWorkspace();
    hide();
    try {
      const token = await request();
      if (epoch !== generation || deps.getToken() !== null) throw superseded();
      if (typeof token !== "string" || !token.trim()) throw new Error("The backend did not return an access_token.");
      deps.setToken(token);
      await verify(epoch);
    } catch (error) {
      if (epoch === generation && !deps.getToken()) publish("anonymous");
      throw error;
    }
  }
  function syncSession() {
    // Do not erase another tab's new token. Hide the old identity/cache first.
    deps.clearWorkspace();
    return refresh();
  }
  return { signOut, refresh, authenticate, syncSession, dispose: () => { generation++; } };
}
