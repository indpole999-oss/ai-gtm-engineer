import { createFileRoute } from "@tanstack/react-router";
import { IntegrationsPage } from "@/components/customer/integrations";
export const Route = createFileRoute("/_authenticated/integrations")({ component: IntegrationsPage, head: () => ({ meta: [{ title: "Integrations — GAPS AI" }] }) });
