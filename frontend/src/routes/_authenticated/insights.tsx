import { createFileRoute } from "@tanstack/react-router";
import { InsightsPage } from "@/components/customer/insights";
export const Route = createFileRoute("/_authenticated/insights")({ component: InsightsPage, head: () => ({ meta: [{ title: "Insights — GAPS AI" }] }) });
