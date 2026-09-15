import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { DataTable, type Column } from "@/components/data-table";
import { DetailPanel } from "@/components/detail-panel";
import { StatusBadge } from "@/components/status-badge";
import { NotConfiguredCard } from "@/components/stage-results";
import { ErrorBlock, LoadingBlock } from "@/components/state-block";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { bookMeeting, getCalendarAuth, isNotConfigured } from "@/lib/gtm-api";
import { rows, text, useMeetings } from "@/lib/gtm-queries";
import { formatValue } from "@/lib/format";

export const Route = createFileRoute("/_authenticated/calendar")({
  head: () => ({
    meta: [
      { title: "Meetings — AI GTM Engineer" },
      { name: "description", content: "Meetings booked by the calendar agent, with real integration status." },
      { property: "og:title", content: "Meetings — AI GTM Engineer" },
      { property: "og:description", content: "Meetings booked by the calendar agent." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: MeetingsPage,
});

type Row = Record<string, unknown>;

function MeetingsPage() {
  const meetings = useMeetings();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Row | null>(null);
  const [form, setForm] = useState({ contact_id: "", title: "", preferred_date: "" });

  const auth = useQuery({ queryKey: ["calendar-auth"], queryFn: getCalendarAuth, retry: false });

  const meetingRows = rows(meetings.data);
  const notConfigured =
    isNotConfigured(meetings.data) ||
    isNotConfigured(auth.data) ||
    (auth.error instanceof ApiError && isNotConfigured(auth.error.detail ?? auth.error.message)) ||
    (meetings.error instanceof ApiError && isNotConfigured(meetings.error.detail ?? meetings.error.message));

  const authUrl =
    auth.data && typeof auth.data === "object"
      ? (["auth_url", "url", "authorization_url"]
          .map((k) => (auth.data as Row)[k])
          .find((v) => typeof v === "string") as string | undefined)
      : undefined;

  const book = useMutation({
    mutationFn: () =>
      bookMeeting({
        contact_id: form.contact_id,
        ...(form.title ? { title: form.title } : {}),
        preferred_date: form.preferred_date || null,
      }),
    onSuccess: (data) => {
      if (isNotConfigured(data)) {
        toast.warning("Calendar integration not configured", {
          description: "The backend could not create a real calendar event.",
        });
      } else {
        toast.success("Meeting request submitted");
      }
      void queryClient.invalidateQueries({ queryKey: ["calendar"] });
    },
    onError: (error: Error) => toast.error("Booking failed", { description: error.message }),
  });

  const columns: Column<Row>[] = [
    {
      key: "title",
      header: "Meeting",
      value: (r) => text(r, ["title", "summary", "name"]),
      render: (r) => <span className="font-medium">{text(r, ["title", "summary", "name"])}</span>,
    },
    { key: "contact_id", header: "Contact", value: (r) => text(r, ["contact_id", "attendee", "email"]) },
    {
      key: "start",
      header: "Start",
      value: (r) => text(r, ["start_time", "scheduled_at", "start", "preferred_date"]),
      render: (r) => formatValue("start_at", r["start_time"] ?? r["scheduled_at"] ?? r["start"] ?? null),
    },
    { key: "duration_minutes", header: "Duration", value: (r) => Number(r["duration_minutes"] ?? 0) },
    {
      key: "status",
      header: "Status",
      value: (r) => text(r, ["status", "state"]),
      render: (r) => <StatusBadge value={text(r, ["status", "state"], "unknown")} />,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Meetings"
        description="Calendar activity created by the meeting agent."
        actions={
          <Button variant="outline" size="sm" onClick={() => meetings.refetch()} disabled={meetings.isFetching}>
            <RefreshCw className={meetings.isFetching ? "size-4 animate-spin" : "size-4"} aria-hidden />
            Refresh
          </Button>
        }
      />

      {notConfigured ? (
        <NotConfiguredCard
          title="Calendar integration not configured"
          description="The backend reports that calendar credentials are missing, so no real events can be created."
        />
      ) : null}

      {authUrl ? (
        <div className="rounded-lg border bg-card p-4 text-sm shadow-xs">
          The backend provided a calendar authorization link.{" "}
          <a className="font-medium text-primary underline-offset-4 hover:underline" href={authUrl} target="_blank" rel="noreferrer">
            Connect calendar
          </a>
        </div>
      ) : null}

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <h2 className="text-sm font-semibold">Book a meeting</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor="m-contact">Contact ID *</Label>
            <Input id="m-contact" value={form.contact_id} onChange={(e) => setForm({ ...form, contact_id: e.target.value })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="m-title">Title</Label>
            <Input id="m-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Discovery Call - AI GTM" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="m-date">Preferred date</Label>
            <Input id="m-date" type="datetime-local" value={form.preferred_date} onChange={(e) => setForm({ ...form, preferred_date: e.target.value })} />
          </div>
        </div>
        <Button className="mt-4" disabled={!form.contact_id.trim() || book.isPending} onClick={() => book.mutate()}>
          {book.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          Book meeting
        </Button>
      </section>

      {meetings.isPending ? (
        <div className="rounded-lg border bg-card">
          <LoadingBlock />
        </div>
      ) : meetings.isError && !notConfigured ? (
        <div className="rounded-lg border bg-card">
          <ErrorBlock error={meetings.error} resourceLabel="meetings" onRetry={() => meetings.refetch()} />
        </div>
      ) : (
        <DataTable
          rows={meetingRows}
          columns={columns}
          onRowClick={setSelected}
          searchPlaceholder="Search meetings"
          emptyTitle="No meetings"
          emptyDescription="No meetings have been booked through the backend yet."
        />
      )}

      <DetailPanel
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
        title="Meeting"
        record={selected}
      />
    </div>
  );
}
