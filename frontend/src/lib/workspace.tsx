import { createContext, useContext, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, setWorkspaceId } from "./api";

type Workspace = { id: string; name: string; role: string };
const Context = createContext<{
  workspace: Workspace;
  workspaces: Workspace[];
  select: (id: string) => void;
} | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const cache = useQueryClient();
  const [selected, setSelected] = useState<Workspace | null>(null);
  const list = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => apiFetch<Workspace[]>("/api/v1/workspaces"),
    retry: false,
  });
  function select(id: string) {
    const next = list.data?.find((w) => w.id === id);
    if (!next) return;
    void cache.cancelQueries();
    cache.removeQueries({ predicate: (q) => q.queryKey[0] !== "workspaces" });
    setWorkspaceId(next.id);
    setSelected(next);
  }
  if (!selected)
    return (
      <main className="mx-auto max-w-lg space-y-5 p-8">
        <p className="eyebrow">GAPS AI</p>
        <h1 className="text-3xl font-semibold">Your workspace</h1>
        {list.isPending ? (
          <p role="status">Loading your workspaces…</p>
        ) : list.isError ? (
          <div role="alert">
            <p>We couldn’t load your workspaces.</p>
            <button className="g-button" onClick={() => void list.refetch()}>
              Try again
            </button>
          </div>
        ) : !list.data?.length ? (
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
