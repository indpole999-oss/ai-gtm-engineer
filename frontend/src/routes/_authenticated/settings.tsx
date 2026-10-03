import { createFileRoute } from "@tanstack/react-router";
import { SettingsPage } from "@/components/customer/settings";
export const Route = createFileRoute("/_authenticated/settings")({ component: SettingsPage, head: () => ({ meta: [{ title: "Settings — GAPS AI" }] }) });
