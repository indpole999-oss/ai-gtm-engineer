import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  Command,
  Inbox,
  LogOut,
  Menu,
  Plug,
  Send,
  Settings,
  Target,
  Workflow,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import { useWorkspace } from "@/lib/workspace";
import { displayName, useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

export const NAV = [
  { to: "/dashboard", label: "Command Center", icon: Command },
  { to: "/prospects", label: "Prospects", icon: Target },
  { to: "/outreach", label: "Outreach", icon: Send },
  { to: "/inbox", label: "Inbox", icon: Inbox },
  { to: "/pipeline", label: "Pipeline", icon: Workflow },
  { to: "/insights", label: "Insights", icon: BarChart3 },
  { to: "/integrations", label: "Integrations", icon: Plug },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Customer navigation" className="space-y-1">
      {NAV.map(({ to, label, icon: Icon }) => (
        <Link
          key={to}
          to={to}
          preload="intent"
          onClick={onNavigate}
          className="g-nav"
          activeProps={{ className: "g-nav" }}
        >
          <Icon className="size-[17px] shrink-0" strokeWidth={1.7} aria-hidden />
          {label}
        </Link>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <span className="flex size-8 items-center justify-center rounded-[9px] bg-primary text-[13px] font-bold text-primary-foreground shadow-[inset_0_1px_0_rgba(255,255,255,.15)]">
        G
      </span>
      <div className="leading-tight">
        <p className="text-sm font-semibold tracking-tight text-sidebar-foreground">GAPS AI</p>
        <p className="mt-0.5 text-[10px] text-muted-foreground">AI GTM employee</p>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth();
  const { workspace, workspaces, select, canApprove } = useWorkspace();
  const location = useLocation();
  const internal = !NAV.some((n) => n.to === location.pathname.replace(/\/$/, ""));
  const operator = import.meta.env["VITE_OPERATOR_UI"] === "true" && canApprove;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mobileOpen, setMobileOpen] = useState(false);

  async function handleSignOut() {
    await queryClient.cancelQueries();
    queryClient.clear();
    signOut();
    navigate({ to: "/login", replace: true });
  }

  return (
    <div className="g-app-frame flex bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:z-50 focus:bg-card focus:p-4"
      >
        Skip to content
      </a>

      <aside className="g-sidebar sticky top-0 hidden h-screen w-[15.5rem] shrink-0 flex-col border-r border-sidebar-border md:flex">
        <div className="px-[22px] py-6">
          <Brand />
        </div>

        <div className="flex-1 overflow-y-auto px-3.5 pb-4 pt-3">
          <NavLinks />
        </div>

        <div className="border-t border-sidebar-border px-4 py-4">
          <label className="block text-[10px] font-semibold uppercase tracking-[.12em] text-muted-foreground">
            Workspace
            <select
              aria-label="Current workspace"
              value={workspace.id}
              onChange={(e) => select(e.target.value)}
              className="g-input mt-2 py-2 text-xs"
            >
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>

          <div className="mt-4 flex items-center gap-3">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold text-secondary-foreground">
              {displayName(user)
                .split(" ")
                .slice(0, 2)
                .map((part) => part[0])
                .join("")
                .toUpperCase() || "A"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium text-sidebar-foreground">
                {displayName(user)}
              </p>
              <p className="truncate text-[10px] text-muted-foreground">{workspace.role} access</p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="size-8 text-muted-foreground hover:bg-secondary hover:text-foreground"
              onClick={handleSignOut}
              aria-label="Sign out"
            >
              <LogOut className="size-4" aria-hidden />
            </Button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="g-topbar flex h-16 items-center justify-between gap-3 border-b px-4 md:hidden">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Open navigation"
                className="text-muted-foreground hover:bg-secondary hover:text-foreground"
              >
                <Menu className="size-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 border-sidebar-border bg-sidebar p-0">
              <SheetHeader className="border-b border-sidebar-border px-5 py-5">
                <SheetTitle asChild>
                  <div>
                    <Brand />
                  </div>
                </SheetTitle>
              </SheetHeader>
              <div className="px-3 py-4">
                <NavLinks onNavigate={() => setMobileOpen(false)} />
                <label className="mt-6 block text-xs font-semibold">
                  Workspace
                  <select
                    aria-label="Current workspace"
                    value={workspace.id}
                    onChange={(event) => {
                      select(event.target.value);
                      setMobileOpen(false);
                    }}
                    className="g-input mt-2 w-full"
                  >
                    {workspaces.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </SheetContent>
          </Sheet>

          <Brand />

          <Button
            variant="ghost"
            size="icon"
            onClick={handleSignOut}
            aria-label="Sign out"
            className="text-muted-foreground hover:bg-secondary hover:text-foreground"
          >
            <LogOut className="size-4" aria-hidden />
          </Button>
        </header>

        <main
          id="main-content"
          tabIndex={-1}
          className="min-w-0 flex-1 px-5 py-8 sm:px-8 md:px-10 md:py-12 xl:px-14"
        >
          <div key={location.pathname} className="g-page mx-auto max-w-[92rem] space-y-9">
            {internal && !operator ? (
              <section className="g-panel max-w-2xl">
                <p className="eyebrow">WORKSPACE</p>
                <h1 className="mt-3 text-2xl font-semibold">
                  This page is not part of your workspace
                </h1>
                <p className="my-4 text-sm leading-6 text-muted-foreground">
                  Your customer tools are available from the main navigation.
                </p>
                <Link to="/dashboard" className="g-button">
                  Return to Command Center
                </Link>
              </section>
            ) : (
              children
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
