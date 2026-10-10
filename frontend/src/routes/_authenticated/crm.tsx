import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { DataTable, type Column } from "@/components/data-table";
import { DetailPanel } from "@/components/detail-panel";
import { StatusBadge } from "@/components/status-badge";
import { NotConfiguredCard } from "@/components/stage-results";
import {
  ErrorBlock,
  LoadingBlock,
} from "@/components/state-block";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import {
  createCrmActivity,
  createCrmCompany,
  createCrmDeal,
  createCrmRecord,
  isNotConfigured,
} from "@/lib/gtm-api";
import {
  rows,
  text,
  useCrm,
} from "@/lib/gtm-queries";
import { formatValue } from "@/lib/format";

export const Route = createFileRoute("/_authenticated/crm")({
  head: () => ({
    meta: [
      {
        title: "CRM — AI GTM Engineer",
      },
      {
        name: "description",
        content:
          "CRM records synced by the AI CRM agent, with real integration status.",
      },
      {
        property: "og:title",
        content: "CRM — AI GTM Engineer",
      },
      {
        property: "og:description",
        content:
          "CRM records synced by the AI CRM agent.",
      },
      {
        property: "og:type",
        content: "website",
      },
      {
        name: "twitter:card",
        content: "summary",
      },
    ],
  }),
  component: CrmPage,
});

type Row = Record<string, unknown>;

function CrmPage() {
  const crm = useCrm();
  const queryClient = useQueryClient();

  const [selected, setSelected] =
    useState<Row | null>(null);

  const [contactId, setContactId] = useState("");
  const [companyId, setCompanyId] = useState("");

  const [dealName, setDealName] = useState("");
  const [dealAmount, setDealAmount] = useState("");
  const [dealStage, setDealStage] =
    useState("appointmentscheduled");
  const [dealPipeline, setDealPipeline] =
    useState("default");
  const [dealCloseDate, setDealCloseDate] =
    useState("");
  const [dealCompanyId, setDealCompanyId] =
    useState("");

  const [activityRecordId, setActivityRecordId] =
    useState("");
  const [activityNote, setActivityNote] =
    useState("");

  const crmRows = rows(crm.data);

  const notConfigured =
    isNotConfigured(crm.data) ||
    (crm.error instanceof ApiError &&
      isNotConfigured(
        crm.error.detail ?? crm.error.message,
      ));

  const push = useMutation({
    mutationFn: (id: string) =>
      createCrmRecord(id),

    onSuccess: (data) => {
      if (isNotConfigured(data)) {
        toast.warning(
          "CRM integration not configured",
          {
            description:
              "The backend accepted the request but no CRM provider is connected.",
          },
        );
      } else {
        toast.success(
          "Contact pushed to CRM",
        );
      }

      void queryClient.invalidateQueries({
        queryKey: ["crm"],
      });
    },

    onError: (error: Error) => {
      toast.error("CRM push failed", {
        description: error.message,
      });
    },
  });

  const pushCompany = useMutation({
    mutationFn: (id: string) =>
      createCrmCompany(id),

    onSuccess: (data) => {
      if (isNotConfigured(data)) {
        toast.warning(
          "CRM integration not configured",
          {
            description:
              "The backend accepted the request but no CRM provider is connected.",
          },
        );
      } else {
        toast.success(
          "Company pushed to CRM",
        );
      }

      void queryClient.invalidateQueries({
        queryKey: ["crm"],
      });
    },

    onError: (error: Error) => {
      toast.error(
        "Company CRM push failed",
        {
          description: error.message,
        },
      );
    },
  });

  const pushDeal = useMutation({
    mutationFn: () =>
      createCrmDeal({
        deal_name: dealName.trim(),
        amount: dealAmount.trim()
          ? Number(dealAmount)
          : null,
        stage:
          dealStage.trim() ||
          "appointmentscheduled",
        pipeline:
          dealPipeline.trim() ||
          "default",
        close_date:
          dealCloseDate.trim() ||
          null,
        company_id:
          dealCompanyId.trim() ||
          null,
      }),

    onSuccess: (data) => {
      if (isNotConfigured(data)) {
        toast.warning(
          "CRM integration not configured",
          {
            description:
              "The backend accepted the request but no CRM provider is connected.",
          },
        );
      } else {
        toast.success(
          "Deal created in CRM",
          {
            description: data?.["deal_id"]
              ? `HubSpot Deal ID: ${String(
                  data["deal_id"],
                )}`
              : undefined,
          },
        );

        setDealName("");
        setDealAmount("");
        setDealCloseDate("");
      }

      void queryClient.invalidateQueries({
        queryKey: ["crm"],
      });
    },

    onError: (error: Error) => {
      toast.error(
        "CRM deal creation failed",
        {
          description: error.message,
        },
      );
    },
  });

  const logActivity = useMutation({
    mutationFn: () =>
      createCrmActivity({
        record_id:
          activityRecordId.trim(),
        note: activityNote.trim(),
      }),

    onSuccess: (data) => {
      if (isNotConfigured(data)) {
        toast.warning(
          "CRM integration not configured",
          {
            description:
              "The backend accepted the request but no CRM provider is connected.",
          },
        );
      } else {
        toast.success(
          "CRM activity logged",
          {
            description: data?.["note_id"]
              ? `HubSpot Note ID: ${String(
                  data["note_id"],
                )}`
              : undefined,
          },
        );

        setActivityNote("");
      }

      void queryClient.invalidateQueries({
        queryKey: ["crm"],
      });
    },

    onError: (error: Error) => {
      toast.error(
        "CRM activity logging failed",
        {
          description: error.message,
        },
      );
    },
  });

  const columns: Column<Row>[] = [
    {
      key: "id",
      header: "Record",
      value: (row) =>
        text(row, [
          "id",
          "external_id",
        ]),
    },
    {
      key: "contact_id",
      header: "Contact",
      value: (row) =>
        text(row, ["contact_id"]),
    },
    {
      key: "company_id",
      header: "Company",
      value: (row) =>
        text(row, ["company_id"]),
    },
    {
      key: "provider",
      header: "Provider",
      value: (row) =>
        text(row, [
          "provider",
          "crm",
          "source",
        ]),
    },
    {
      key: "status",
      header: "Status",
      value: (row) =>
        text(
          row,
          [
            "status",
            "state",
            "sync_status",
          ],
          "unknown",
        ),
      render: (row) => (
        <StatusBadge
          value={text(
            row,
            [
              "status",
              "state",
              "sync_status",
            ],
            "unknown",
          )}
        />
      ),
    },
    {
      key: "created_at",
      header: "Synced",
      value: (row) =>
        text(row, [
          "created_at",
          "synced_at",
          "updated_at",
        ]),
      render: (row) =>
        formatValue(
          "created_at",
          row["created_at"] ??
            row["synced_at"] ??
            row["updated_at"] ??
            null,
        ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="CRM"
        description="Records the CRM agent has pushed to your connected CRM provider."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              void crm.refetch()
            }
            disabled={crm.isFetching}
          >
            <RefreshCw
              className={
                crm.isFetching
                  ? "size-4 animate-spin"
                  : "size-4"
              }
              aria-hidden
            />
            Refresh
          </Button>
        }
      />

      {notConfigured ? (
        <NotConfiguredCard
          title="CRM integration not configured"
          description="The backend reports that no CRM provider is connected. Configure CRM credentials on the server; nothing is being synced right now."
        />
      ) : null}

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <h2 className="text-sm font-semibold">
          Push a contact to CRM
        </h2>

        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div className="min-w-64 flex-1 space-y-1.5">
            <Label htmlFor="crm-contact">
              Contact ID
            </Label>

            <Input
              id="crm-contact"
              value={contactId}
              onChange={(event) =>
                setContactId(
                  event.target.value,
                )
              }
              placeholder="Contact ID"
            />
          </div>

          <Button
            disabled={
              !contactId.trim() ||
              push.isPending
            }
            onClick={() =>
              push.mutate(
                contactId.trim(),
              )
            }
          >
            {push.isPending ? (
              <Loader2
                className="size-4 animate-spin"
                aria-hidden
              />
            ) : null}
            Push to CRM
          </Button>
        </div>
      </section>

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <h2 className="text-sm font-semibold">
          Push a company to CRM
        </h2>

        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div className="min-w-64 flex-1 space-y-1.5">
            <Label htmlFor="crm-company">
              Company ID
            </Label>

            <Input
              id="crm-company"
              value={companyId}
              onChange={(event) =>
                setCompanyId(
                  event.target.value,
                )
              }
              placeholder="Company ID"
            />
          </div>

          <Button
            disabled={
              !companyId.trim() ||
              pushCompany.isPending
            }
            onClick={() =>
              pushCompany.mutate(
                companyId.trim(),
              )
            }
          >
            {pushCompany.isPending ? (
              <Loader2
                className="size-4 animate-spin"
                aria-hidden
              />
            ) : null}
            Push Company to CRM
          </Button>
        </div>
      </section>

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <h2 className="text-sm font-semibold">
          Create a deal in CRM
        </h2>

        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="crm-deal-name">
              Deal Name
            </Label>

            <Input
              id="crm-deal-name"
              value={dealName}
              onChange={(event) =>
                setDealName(
                  event.target.value,
                )
              }
              placeholder="OpenAI Test Deal"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="crm-deal-amount">
              Amount
            </Label>

            <Input
              id="crm-deal-amount"
              type="number"
              min="0"
              value={dealAmount}
              onChange={(event) =>
                setDealAmount(
                  event.target.value,
                )
              }
              placeholder="10000"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="crm-deal-stage">
              Deal Stage
            </Label>

            <Input
              id="crm-deal-stage"
              value={dealStage}
              onChange={(event) =>
                setDealStage(
                  event.target.value,
                )
              }
              placeholder="appointmentscheduled"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="crm-deal-pipeline">
              Pipeline
            </Label>

            <Input
              id="crm-deal-pipeline"
              value={dealPipeline}
              onChange={(event) =>
                setDealPipeline(
                  event.target.value,
                )
              }
              placeholder="default"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="crm-deal-close-date">
              Close Date
            </Label>

            <Input
              id="crm-deal-close-date"
              type="date"
              value={dealCloseDate}
              onChange={(event) =>
                setDealCloseDate(
                  event.target.value,
                )
              }
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="crm-deal-company">
              Company ID
            </Label>

            <Input
              id="crm-deal-company"
              value={dealCompanyId}
              onChange={(event) =>
                setDealCompanyId(
                  event.target.value,
                )
              }
              placeholder="Optional local Company ID"
            />
          </div>
        </div>

        <div className="mt-4">
          <Button
            disabled={
              !dealName.trim() ||
              pushDeal.isPending
            }
            onClick={() =>
              pushDeal.mutate()
            }
          >
            {pushDeal.isPending ? (
              <Loader2
                className="size-4 animate-spin"
                aria-hidden
              />
            ) : null}
            Create Deal in CRM
          </Button>
        </div>
      </section>

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <div>
          <h2 className="text-sm font-semibold">
            Log CRM activity
          </h2>

          <p className="mt-1 text-sm text-muted-foreground">
            Add a note or activity to an existing
            HubSpot contact.
          </p>
        </div>

        <div className="mt-4 space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="crm-activity-record">
              HubSpot Contact ID
            </Label>

            <Input
              id="crm-activity-record"
              value={activityRecordId}
              onChange={(event) =>
                setActivityRecordId(
                  event.target.value,
                )
              }
              placeholder="HubSpot contact ID"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="crm-activity-note">
              Activity Note
            </Label>

            <Textarea
              id="crm-activity-note"
              value={activityNote}
              onChange={(event) =>
                setActivityNote(
                  event.target.value,
                )
              }
              placeholder="Example: Followed up with prospect regarding demo."
              rows={4}
            />
          </div>

          <Button
            disabled={
              logActivity.isPending ||
              !activityRecordId.trim() ||
              !activityNote.trim()
            }
            onClick={() =>
              logActivity.mutate()
            }
          >
            {logActivity.isPending ? (
              <Loader2
                className="size-4 animate-spin"
                aria-hidden
              />
            ) : null}
            Log Activity
          </Button>
        </div>
      </section>

      {crm.isPending ? (
        <div className="rounded-lg border bg-card">
          <LoadingBlock />
        </div>
      ) : crm.isError &&
        !notConfigured ? (
        <div className="rounded-lg border bg-card">
          <ErrorBlock
            error={crm.error}
            resourceLabel="CRM records"
            onRetry={() =>
              void crm.refetch()
            }
          />
        </div>
      ) : (
        <DataTable
          rows={crmRows}
          columns={columns}
          onRowClick={setSelected}
          searchPlaceholder="Search CRM records"
          emptyTitle="No CRM records"
          emptyDescription="Nothing has been synced to a CRM yet."
        />
      )}

      <DetailPanel
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSelected(null);
          }
        }}
        title="CRM record"
        record={selected}
      />
    </div>
  );
}
