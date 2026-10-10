import { createFileRoute, Link } from "@tanstack/react-router";
import { Bot, Mail, Target, Workflow } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "GAPS AI â€” Evidence-backed growth" },
      {
        name: "description",
        content:
          "A clear workspace for evidence-backed prospects, reviewed outreach, customer conversations and measured growth.",
      },
      { property: "og:title", content: "GAPS AI â€” Evidence-backed growth" },
      {
        property: "og:description",
        content: "Your prospects, outreach, conversations and insights in one considered workspace.",
      },
    ],
  }),
  component: Landing,
});

const PILLARS = [
  { icon: Target, title: "Pipeline", body: "Leads, companies and contacts unified in one working surface." },
  { icon: Workflow, title: "Your plan", body: "Review each step before approving the work." },
  { icon: Mail, title: "Sequences", body: "Outbound cadences with live send and reply status." },
  { icon: Bot, title: "Insights", body: "Evidence-backed recommendations with transparent limitations." },
];

function Landing() {
  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="absolute inset-0 grid-backdrop opacity-30" aria-hidden />
      <div className="relative mx-auto flex min-h-screen max-w-5xl flex-col px-6 py-8">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-md bg-primary font-display text-sm font-bold text-primary-foreground">
              G
            </span>
            <span className="font-display text-sm font-semibold">GAPS AI</span>
          </div>
          <Link
            to="/login"
            className="rounded-md border px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
          >
            Sign in
          </Link>
        </header>

        <main className="flex flex-1 flex-col justify-center py-16">
          <p className="label-mono">EVIDENCE. INTENTION. PROGRESS.</p>
          <h1 className="mt-3 max-w-2xl text-4xl font-semibold leading-tight md:text-5xl">
            Your next customer starts with a clearer picture.
          </h1>
          <p className="mt-4 max-w-xl text-base text-muted-foreground">
            Understand your prospects, prepare thoughtful outreach, and measure real outcomes — with your team in control.
          </p>
          <div className="mt-8">
            <Link
              to="/login"
              className="inline-flex items-center justify-center rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
            >
              Enter your workspace
            </Link>
          </div>

          <div className="mt-16 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {PILLARS.map(({ icon: Icon, title, body }) => (
              <div key={title} className="rounded-xl border bg-card p-4">
                <Icon className="size-5 text-primary" aria-hidden />
                <h2 className="mt-3 font-display text-sm font-semibold">{title}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>
        </main>

        <footer className="label-mono">GAPS AI · Thoughtful growth</footer>
      </div>
    </div>
  );
}
