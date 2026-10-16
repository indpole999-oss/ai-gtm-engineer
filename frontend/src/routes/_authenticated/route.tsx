import { Outlet, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

import { AppShell } from "@/components/app-shell";
import { InlineSpinner } from "@/components/state-block";
import { useAuth } from "@/lib/auth";
import { WorkspaceProvider } from "@/lib/workspace";

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  component: AuthenticatedLayout,
});

function AuthenticatedLayout() {
  const { status, user, refresh, signOut } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (status === "anonymous") {
      navigate({ to: "/login", replace: true });
    }
  }, [status, navigate]);

  if (status === "unavailable") {
    return (
      <main className="mx-auto max-w-lg space-y-5 p-8">
        <h1 className="text-3xl font-semibold">Account verification unavailable</h1>
        <p role="alert">We couldn’t verify your account. Your workspace data stays hidden until verification succeeds.</p>
        <button className="g-button" onClick={() => void refresh()}>Try again</button>
        <button className="block text-sm underline" onClick={signOut}>Back to sign in</button>
      </main>
    );
  }

  if (status !== "authenticated" || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <InlineSpinner label={status === "loading" ? "Restoring session…" : "Redirecting to sign in…"} />
      </div>
    );
  }

  return (
    <WorkspaceProvider key={String(user.id)}><AppShell>
      <Outlet />
    </AppShell></WorkspaceProvider>
  );
}
