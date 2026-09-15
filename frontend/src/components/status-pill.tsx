import { cn } from "@/lib/utils";
import { statusTone } from "@/lib/format";

export function StatusPill({ value }: { value: unknown }) {
  const tone = statusTone(value);
  const text =
    typeof value === "boolean" ? (value ? "Active" : "Inactive") : String(value).replace(/_/g, " ");

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-wider",
        tone === "success" && "border-success/30 bg-success/10 text-success",
        tone === "warning" && "border-warning/30 bg-warning/10 text-warning",
        tone === "danger" && "border-destructive/30 bg-destructive/10 text-destructive",
        tone === "neutral" && "border-border bg-muted text-muted-foreground",
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          tone === "success" && "bg-success",
          tone === "warning" && "bg-warning",
          tone === "danger" && "bg-destructive",
          tone === "neutral" && "bg-muted-foreground",
        )}
      />
      {text}
    </span>
  );
}
