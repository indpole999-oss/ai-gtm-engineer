import { createFileRoute } from "@tanstack/react-router";
import { ProspectsPage } from "@/components/customer/prospects";
export const Route = createFileRoute("/_authenticated/prospects")({ component: ProspectsPage, head: () => ({ meta: [{ title: "Prospects — GAPS AI" }] }) });
