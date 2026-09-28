import { createFileRoute } from "@tanstack/react-router";
import { PipelinePage } from "@/components/customer/pipeline";
export const Route = createFileRoute("/_authenticated/pipeline")({ component: PipelinePage, head: () => ({ meta: [{ title: "Pipeline — GAPS AI" }] }) });
