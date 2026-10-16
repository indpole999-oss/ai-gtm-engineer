import { useState } from "react";
import { Heading, Panel, Status, Loading, ErrorState, useData, Field, time } from "./ui";
import { percent, type Insights, type Recommendation } from "./contracts";

export function RecommendationCard({ item }: { item: Recommendation }) {
  return (
    <Panel>
      <div className="flex flex-wrap justify-between gap-3">
        <h3 className="font-semibold capitalize">{item.rule.replaceAll("_", " ")}</h3>
        <Status value={item.status} />
      </div>
      <p className="mt-4 text-sm leading-6">
        {item.observed_gap ||
          (item.status === "insufficient_data"
            ? "More complete evidence is needed before making a recommendation."
            : "No gap observed at the configured review threshold.")}
      </p>
      <p className="mt-3 text-sm text-muted-foreground">
        {item.supporting_metric.numerator} / {item.supporting_metric.denominator} ·{" "}
        {item.confidence.replaceAll("_", " ")}
      </p>
      <p className="mt-4 text-sm font-medium">{item.proposed_action}</p>
      <p className="mt-3 text-xs text-muted-foreground">
        Advice only · Separate review and approval required
      </p>
      <details className="mt-5 text-sm">
        <summary>Evidence & limitations</summary>
        <div className="mt-3 space-y-3 text-muted-foreground">
          <p>
            Sample: {item.sample_size}. {item.expected_outcome}
          </p>
          <p>
            Cost: {item.cost.status}. Risk: {item.risk}
          </p>
          <ul className="list-inside list-disc">
            {item.limitations.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <p className="break-all">
            Included records: {item.supporting_metric.denominator_ids.join(", ") || "None"}
          </p>
          <p className="break-all">
            Observed outcomes: {item.supporting_metric.numerator_ids.join(", ") || "None"}
          </p>
        </div>
      </details>
    </Panel>
  );
}

export function InsightsPage() {
  const [range, setRange] = useState(() => ({
    start: new Date(Date.now() - 30 * 86400000).toISOString(),
    end: new Date().toISOString(),
  }));
  const [start, setStart] = useState(range.start.slice(0, 10));
  const [end, setEnd] = useState(range.end.slice(0, 10));
  const [entity, setEntity] = useState("contact");
  const [dimension, setDimension] = useState("campaign_id");
  const path = `/api/v1/insights?start=${encodeURIComponent(range.start)}&end=${encodeURIComponent(range.end)}&entity_type=${entity}`;
  const query = useData<Insights>(path);
  const report = query.data;
  return (
    <>
      <Heading
        title="Insights"
        description="Understand what happened. Find the next question worth asking. Every outcome is grounded in your workspace’s evidence."
      />
      <form
        className="g-panel flex flex-wrap items-end gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          const cutoff = Math.min(new Date(end + "T00:00:00Z").valueOf() + 86400000, Date.now());
          setRange({ start: start + "T00:00:00.000Z", end: new Date(cutoff).toISOString() });
        }}
      >
        <Field label="From (UTC)">
          <input
            className="g-input"
            type="date"
            required
            value={start}
            max={end}
            onChange={(e) => setStart(e.target.value)}
          />
        </Field>
        <Field label="Through (UTC)">
          <input
            className="g-input"
            type="date"
            required
            value={end}
            min={start}
            max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => setEnd(e.target.value)}
          />
        </Field>
        <Field label="Funnel cohort">
          <select className="g-input" value={entity} onChange={(e) => setEntity(e.target.value)}>
            <option value="contact">Contacts</option>
            <option value="account">Accounts</option>
          </select>
        </Field>
        <button className="g-button">Apply dates</button>
      </form>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        report && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {[
                ["Provider-confirmed sends", report.metrics.outreach.sent],
                ["Human replies", report.metrics.outreach.reply.numerator],
                [
                  "Confirmed meeting conversion",
                  percent(report.metrics.contacted_to_confirmed_meeting),
                ],
                ["Pipeline cohort", report.funnel.sample_size],
              ].map(([label, value]) => (
                <Panel key={label}>
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="mt-4 text-3xl font-semibold tracking-tight">{value}</p>
                  {label === "Confirmed meeting conversion" && <div className="mt-3 text-xs text-muted-foreground">
                    {report.metrics.contacted_to_confirmed_meeting.numerator}/{report.metrics.contacted_to_confirmed_meeting.denominator} observed · <Status value={report.metrics.contacted_to_confirmed_meeting.status}/>
                  </div>}
                </Panel>
              ))}
            </div>
            <Panel title="Your funnel">
              <p className="mb-5 text-sm text-muted-foreground">
                {report.funnel.cohort}. Historical stage entries; skipped stages are not inferred.
              </p>
              <div className="grid grid-cols-3 gap-3 lg:grid-cols-9">
                {Object.entries(report.funnel.observed_stage_entries).map(([stage, count]) => (
                  <div key={stage} className="rounded-xl bg-muted p-3">
                    <p className="text-xs capitalize">{stage}</p>
                    <p className="mt-3 text-xl font-semibold">{count}</p>
                  </div>
                ))}
              </div>
              <details className="mt-5 text-sm">
                <summary>Conversion denominators and current stages</summary>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  {Object.entries(report.funnel.conversions).map(([name, m]) => (
                    <div key={name}>
                      <p className="capitalize">{name.replaceAll("_", " ")}</p>
                      <p>
                        {percent(m)} · {m.numerator}/{m.denominator} <Status value={m.status} />
                      </p>
                    </div>
                  ))}
                </div>
                <p className="mt-4">
                  Current stages after corrections:{" "}
                  {Object.entries(report.funnel.current_stage_as_of_end)
                    .map(([s, n]) => `${s}: ${n}`)
                    .join(" · ")}
                </p>
                <p>Ambiguous current stages: {report.funnel.ambiguous_current_stage_ids.length}</p>
              </details>
            </Panel>
            <Panel title="Performance by audience & outreach">
              <Field label="Group by">
                <select
                  className="g-input max-w-sm"
                  value={dimension}
                  onChange={(e) => setDimension(e.target.value)}
                >
                  {Object.keys(report.breakdowns).map((d) => (
                    <option key={d} value={d}>
                      {d.replaceAll("_id", "").replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </Field>
              <p className="mt-4 text-sm text-muted-foreground">
                Provider-confirmed message cohort. Unknown dimensions stay unknown.{" "}
                <Status value={report.breakdowns[dimension]?.status} />
              </p>
              <div className="mt-5 space-y-4">
                {report.breakdowns[dimension]?.groups.length ? (
                  report.breakdowns[dimension].groups.map((g) => (
                    <div key={g.value} className="grid gap-3 border-t pt-4 sm:grid-cols-3">
                      <p className="break-all text-sm font-medium">{g.value}</p>
                      <p className="text-sm">
                        {g.sent} sent · {g.reply.numerator}/{g.reply.denominator} replied{" "}
                        <Status value={g.reply.status} />
                      </p>
                      <p className="text-sm">
                        {g.positive_reply.numerator}/{g.positive_reply.denominator} positive
                      </p>
                    </div>
                  ))
                ) : (
                  <p>No messages in this period. Performance is not yet available.</p>
                )}
              </div>
            </Panel>
            <div>
              <p className="eyebrow mb-3">GTM GAP INTELLIGENCE · ADVISORY ONLY</p>
              <div className="grid gap-4 lg:grid-cols-3">
                {report.recommendations.map((r) => (
                  <RecommendationCard key={r.rule} item={r} />
                ))}
              </div>
            </div>
            <Panel title="Coverage & measurement limits">
              <div className="grid gap-5 sm:grid-cols-2">
                {[
                  ["Account research", report.metrics.account_research_coverage],
                  ["Confirmed CRM sync", report.metrics.crm_confirmed_sync_coverage],
                ].map(
                  ([label, m]) =>
                    m &&
                    typeof m !== "string" && (
                      <p key={String(label)}>
                        {String(label)}: {m.numerator}/{m.denominator} <Status value={m.status} />
                      </p>
                    ),
                )}
              </div>
              <p className="mt-5 text-sm">
                Cost per meeting:{" "}
                {report.cost_per_meeting.value === null
                  ? "Unavailable — no actual cost ledger"
                  : report.cost_per_meeting.value}
                . Revenue:{" "}
                {report.revenue.value === null
                  ? "Unavailable — won stages are not booked revenue"
                  : report.revenue.value}
                .
              </p>
              <details className="mt-5 text-sm">
                <summary>Report evidence, dates & limitations</summary>
                <p className="my-3">
                  {time(report.date_range.start)} to {time(report.date_range.end_exclusive)} (end
                  exclusive). Generated {time(report.generated_at)}.
                </p>
                <ul className="list-inside list-disc">
                  {report.limitations.map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                </ul>
                <p className="mt-3 break-all">
                  Report {report.version} · {report.report_hash}
                </p>
                <ol className="mt-4 max-h-64 space-y-2 overflow-auto">
                  {report.evidence_manifest.map((e) => (
                    <li key={e.id} className="break-all">
                      {e.kind.replaceAll("_", " ")} · {time(e.occurred_at)} · Evidence {e.source.id}
                    </li>
                  ))}
                </ol>
              </details>
            </Panel>
          </>
        )
      )}
    </>
  );
}
