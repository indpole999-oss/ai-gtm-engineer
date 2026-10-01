import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, getWorkspaceId, setWorkspaceId } from "./api";

type Workspace = { id: string; name: string; role: string };

const Context = createContext<{
  workspace: Workspace;
  workspaces: Workspace[];
  select: (id: string) => void;
} | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const cache = useQueryClient();
  const [selected, setSelected] = useState<Workspace | null>(null);
  const [restoreChecked, setRestoreChecked] = useState(false);

  const list = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => apiFetch<Workspace[]>("/api/v1/workspaces"),
    retry: false,
  });

  useEffect(() => {
    if (!list.data || selected || restoreChecked) return;

    const storedId = getWorkspaceId();
    if (storedId) {
      const restored = list.data.find((workspace) => workspace.id === storedId);
      if (restored) {
        setWorkspaceId(restored.id);
        setSelected(restored);
      } else {
        // Membership may have changed; never keep a stale workspace identifier.
        setWorkspaceId(null);
      }
    }

    setRestoreChecked(true);
  }, [list.data, selected, restoreChecked]);

  function select(id: string) {
    const next = list.data?.find((w) => w.id === id);
    if (!next) return;

    void cache.cancelQueries();
    cache.removeQueries({ predicate: (q) => q.queryKey[0] !== "workspaces" });
    setWorkspaceId(next.id);
    setSelected(next);
    setRestoreChecked(true);
  }

  if (list.isPending || (!restoreChecked && !list.isError)) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-6">
        <div className="g-panel w-full max-w-sm text-center">
          <p className="eyebrow">GAPS AI</p>
          <p className="mt-3 text-sm text-muted-foreground">Restoring your workspace…</p>
        </div>
      </main>
    );
  }

  if (list.isError) {
    return (
      <main className="mx-auto max-w-lg space-y-5 p-8">
        <p className="eyebrow">GAPS AI</p>
        <h1 className="text-3xl font-semibold">Your workspace</h1>
        <div role="alert">
          <p>We couldn’t load your workspaces.</p>
          <button className="g-button mt-4" onClick={() => void list.refetch()}>
            Try again
          </button>
        </div>
        <a className="text-sm underline" href="/login">
          Back to sign in
        </a>
      </main>
    );
  }

  if (!selected) {
    return (
      <main className="mx-auto max-w-lg space-y-5 p-8">
        <p className="eyebrow">GAPS AI</p>
        <h1 className="text-3xl font-semibold">Your workspace</h1>
        {!list.data?.length ? (
          <p>No active workspace is available. Ask your workspace owner for access.</p>
        ) : (
          list.data.map((w) => (
            <button
              key={w.id}
              className="g-panel block w-full text-left"
              onClick={() => select(w.id)}
            >
              <strong>{w.name}</strong>
              <span className="block text-sm text-muted-foreground">
                {w.role} · Open workspace →
              </span>
            </button>
          ))
        )}
        <a className="text-sm underline" href="/login">
          Back to sign in
        </a>
      </main>
    );
  }

  return (
    <Context.Provider value={{ workspace: selected, workspaces: list.data || [], select }}>
      <div key={selected.id}>{children}</div>
    </Context.Provider>
  );
}

export function useWorkspace() {
  const context = useContext(Context);
  if (!context) throw new Error("Workspace required");

  return {
    ...context,
    canEdit: ["owner", "admin", "member"].includes(context.workspace.role),
    canApprove: ["owner", "admin"].includes(context.workspace.role),
  };
}
