import { createFileRoute } from "@tanstack/react-router";
import { OutreachPage } from "@/components/customer/outreach";
export const Route = createFileRoute("/_authenticated/outreach")({ component: OutreachPage, head: () => ({ meta: [{ title: "Outreach — GAPS AI" }] }) });
