import type { ReactNode } from "react";

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { formatValue, humanizeKey } from "@/lib/format";

export function DetailPanel({
  open,
  onOpenChange,
  title,
  description,
  record,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  record?: Record<string, unknown> | null;
  children?: ReactNode;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>{description ?? "Data exactly as returned by the backend."}</SheetDescription>
        </SheetHeader>
        <div className="space-y-5 px-4 pb-10">
          {children}
          {record ? (
            <dl className="space-y-3">
              {Object.entries(record).map(([key, value]) => (
                <div key={key} className="border-b pb-3 last:border-0">
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {humanizeKey(key)}
                  </dt>
                  <dd className="mt-1 break-words text-sm">
                    {value !== null && typeof value === "object" ? (
                      <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs">
                        {JSON.stringify(value, null, 2)}
                      </pre>
                    ) : (
                      formatValue(key, value)
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
