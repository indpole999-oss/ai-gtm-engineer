import { Link, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  LayoutDashboard,
  LogOut,
  Mail,
  Menu,
  Settings,
  Target,
  Inbox,
  Plug,
  ChartNoAxesCombined,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import { useWorkspace } from "@/lib/workspace";
import { useLocation } from "@tanstack/react-router";
import { displayName, useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

export const NAV = [
  { to: "/dashboard", label: "AI GTM", icon: LayoutDashboard },
  { to: "/prospects", label: "Prospects", icon: Target },
  { to: "/outreach", label: "Outreach", icon: Mail },
  { to: "/inbox", label: "Inbox", icon: Inbox },
  { to: "/pipeline", label: "Pipeline", icon: Building2 },
  { to: "/insights", label: "Insights", icon: ChartNoAxesCombined },
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
          className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-sidebar-foreground/75 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          activeProps={{
            className:
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm bg-sidebar-accent text-sidebar-accent-foreground font-medium",
          }}
        >
          <Icon className="size-4 shrink-0" aria-hidden />
          {label}
        </Link>
      ))}
    </nav>
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

  const brand = (
    <div className="flex items-center gap-2.5">
      <span className="flex size-8 items-center justify-center rounded-md bg-sidebar-primary text-sm font-bold text-sidebar-primary-foreground">
        G
      </span>
      <div className="leading-tight">
        <p className="text-sm font-semibold text-sidebar-foreground">GAPS AI</p>
        <p className="text-[11px] text-sidebar-foreground/60">Your growth, with clarity.</p>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:z-50 focus:bg-card focus:p-4"
      >
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r bg-sidebar md:flex">
        <div className="px-5 py-5">{brand}</div>
        <div className="flex-1 overflow-y-auto px-3 pb-4">
          <NavLinks />
        </div>
        <div className="border-t border-sidebar-border px-3 py-3">
          <p className="truncate px-2 text-sm font-medium text-sidebar-foreground">
            {displayName(user)}
          </p>
          <p className="px-2 text-xs text-muted-foreground">{workspace.role} access</p>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2 w-full justify-start text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            onClick={handleSignOut}
          >
            <LogOut className="size-4" aria-hidden /> Sign out
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b bg-card px-4 py-3 md:hidden">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" aria-label="Open navigation">
                <Menu className="size-4" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 bg-sidebar p-0">
              <SheetHeader className="px-5 py-5">
                <SheetTitle asChild>{brand}</SheetTitle>
              </SheetHeader>
              <div className="px-3">
                <NavLinks onNavigate={() => setMobileOpen(false)} />
              </div>
            </SheetContent>
          </Sheet>
          <span className="text-sm font-semibold">GAPS AI</span>
          <Button variant="ghost" size="sm" onClick={handleSignOut} aria-label="Sign out">
            <LogOut className="size-4" aria-hidden />
          </Button>
        </header>
        <div className="flex items-center justify-end border-b bg-card px-5 py-4">
          <label className="flex items-center gap-3 text-xs text-muted-foreground">
            Workspace
            <select
              aria-label="Current workspace"
              value={workspace.id}
              onChange={(e) => select(e.target.value)}
              className="max-w-52 rounded-lg border bg-card px-3 py-2 text-sm text-foreground"
            >
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <main
          id="main-content"
          tabIndex={-1}
          className="min-w-0 flex-1 px-5 py-8 md:px-10 md:py-12"
        >
          <div key={location.pathname} className="g-page mx-auto max-w-7xl space-y-8">
            {internal && !operator ? (
              <section className="g-panel">
                <h1 className="text-2xl font-semibold">This page is not part of your workspace</h1>
                <p className="my-4 text-muted-foreground">
                  Your customer tools are available in the navigation.
                </p>
                <Link to="/dashboard" className="g-button">
                  Return to AI GTM
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
