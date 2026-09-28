import { createFileRoute } from "@tanstack/react-router";
import { InboxPage } from "@/components/customer/inbox";
export const Route = createFileRoute("/_authenticated/inbox")({ component: InboxPage, head: () => ({ meta: [{ title: "Inbox — GAPS AI" }] }) });
