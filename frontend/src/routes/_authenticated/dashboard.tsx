import { createFileRoute } from "@tanstack/react-router";
import { DashboardPage } from "@/components/customer/dashboard";
export const Route = createFileRoute("/_authenticated/dashboard")({ component: DashboardPage, head: () => ({ meta: [{ title: "AI GTM — GAPS AI" }] }) });
