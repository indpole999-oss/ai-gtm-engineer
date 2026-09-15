import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";

import { API_BASE_URL, AUTH_ENDPOINTS } from "@/lib/api-config";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/login")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Sign in — AI GTM Engineer" },
      { name: "description", content: "Sign in to the AI GTM Engineer console to run pipeline, sequences and agents." },
      { property: "og:title", content: "Sign in — AI GTM Engineer" },
      { property: "og:description", content: "Sign in to the AI GTM Engineer console." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const { signIn, signUp, status } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated") navigate({ to: "/dashboard", replace: true });
  }, [status, navigate]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "signin") await signIn(username, password);
      else await signUp(username, password, fullName);
      navigate({ to: "/dashboard", replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between border-r p-10 lg:flex">
        <div className="absolute inset-0 grid-backdrop opacity-40" aria-hidden />
        <div className="relative">
          <span className="flex size-9 items-center justify-center rounded-md bg-primary font-display text-sm font-bold text-primary-foreground">
            GTM
          </span>
        </div>
        <div className="relative max-w-md">
          <h2 className="text-3xl font-semibold">Pipeline that runs itself.</h2>
          <p className="mt-3 text-sm text-muted-foreground">
            Leads, accounts, emails and autonomous agents — one operations console on top of your GTM
            backend.
          </p>
        </div>
        <p className="relative label-mono">Connected to {API_BASE_URL}</p>
      </div>

      <div className="flex items-center justify-center px-6 py-16">
        <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5">
          <div>
            <p className="label-mono">Authentication</p>
            <h1 className="mt-1 text-2xl font-semibold">
              {mode === "signin" ? "Sign in" : "Create account"}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {mode === "signin" ? "OAuth2 password flow at " : "Registers via "}
              <span className="font-mono text-xs">
                {mode === "signin" ? AUTH_ENDPOINTS.token : AUTH_ENDPOINTS.register}
              </span>
              .
            </p>
          </div>

          {mode === "register" ? (
            <div className="space-y-2">
              <Label htmlFor="fullName">Full name</Label>
              <Input
                id="fullName"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
              />
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="username">Email</Label>
            <Input
              id="username"
              type="email"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              required
            />
          </div>

          {error ? (
            <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          ) : null}

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
            {submitting
              ? mode === "signin"
                ? "Signing in…"
                : "Creating account…"
              : mode === "signin"
                ? "Sign in"
                : "Create account"}
          </Button>

          <button
            type="button"
            className="w-full text-center text-sm text-muted-foreground underline-offset-4 hover:underline"
            onClick={() => {
              setError(null);
              setMode(mode === "signin" ? "register" : "signin");
            }}
          >
            {mode === "signin" ? "No account? Register" : "Already have an account? Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
