import { Link, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Building2,
  CalendarDays,
  Contact2,
  Database,
  LayoutDashboard,
  LogOut,
  Mail,
  Menu,
  Settings,
  Target,
  Workflow,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import { API_BASE_URL } from "@/lib/api-config";
import { displayName, useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/leads", label: "Leads", icon: Target },
  { to: "/companies", label: "Companies", icon: Building2 },
  { to: "/contacts", label: "Contacts", icon: Contact2 },
  { to: "/sequences", label: "Email Sequences", icon: Mail },
  { to: "/workflows", label: "Workflows", icon: Workflow },
  { to: "/agents", label: "AI Agents", icon: Bot },
  { to: "/crm", label: "CRM", icon: Database },
  { to: "/calendar", label: "Meetings", icon: CalendarDays },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="space-y-0.5">
      {NAV.map(({ to, label, icon: Icon }) => (
        <Link
          key={to}
          to={to}
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
        <p className="text-sm font-semibold text-sidebar-foreground">AI GTM Engineer</p>
        <p className="text-[11px] text-sidebar-foreground/60">Go-to-market OS</p>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-sidebar md:flex">
        <div className="px-5 py-5">{brand}</div>
        <div className="flex-1 overflow-y-auto px-3 pb-4">
          <NavLinks />
        </div>
        <div className="border-t border-sidebar-border px-3 py-3">
          <p className="truncate px-2 text-sm font-medium text-sidebar-foreground">{displayName(user)}</p>
          <p className="truncate px-2 font-mono text-[11px] text-sidebar-foreground/50">{API_BASE_URL}</p>
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
          <span className="text-sm font-semibold">AI GTM Engineer</span>
          <Button variant="ghost" size="sm" onClick={handleSignOut} aria-label="Sign out">
            <LogOut className="size-4" aria-hidden />
          </Button>
        </header>
        <main className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
          <div className="mx-auto max-w-7xl space-y-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
