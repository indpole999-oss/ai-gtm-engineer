import { CompanyBrainEditor } from "@/components/company-brain";
import { useWorkspace } from "@/lib/workspace";
import { Heading, Panel } from "./ui";
export function SettingsPage() {
  const { workspace } = useWorkspace();
  return (
    <>
      <Heading
        title="Your company, clearly understood."
        description="Give GAPS AI the context to make grounded recommendations. Draft thoughtfully, review your claims, and publish a version you trust."
      />
      <div className="grid gap-4 md:grid-cols-3">
        {[
          ["01", "Define your market", "Company, product, ICP, personas and geography."],
          ["02", "Ground your claims", "Positioning, evidence, approved and prohibited claims."],
          ["03", "Review & publish", "A fixed version for each future plan and message."],
        ].map(([n, t, d]) => (
          <Panel key={n}>
            <p className="eyebrow">{n}</p>
            <h2 className="mt-3 font-semibold">{t}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{d}</p>
          </Panel>
        ))}
      </div>
      <CompanyBrainEditor />
      <Panel title="Workspace access">
        <p className="text-sm">
          {workspace.name} · {workspace.role}
        </p>
        <p className="mt-3 text-sm text-muted-foreground">
          Owners and admins review publication and outbound execution. Members can prepare work.
          Viewers have read-only access.
        </p>
      </Panel>
    </>
  );
}
